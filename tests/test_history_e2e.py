"""End to end: v1.3 Part 2 "Done when", state and history of a real server across a restart."""
import contextlib
import os
import re
import sqlite3
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)

from e2e import SERVER_DIR, free_port, wait_for, with_system  # noqa: E402

TOKEN = "s3cret-history"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def read_db(system, sql):
    uri = "file:" + os.path.join(system.tmp, "pyhome.db").replace("\\", "/") + "?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as db:
        return db.execute(sql).fetchall()


def history(system):
    return [source for (source,) in read_db(system, "SELECT source FROM state_history ORDER BY id")]


def test_history_from_every_source_and_across_a_restart(tmp):
    def scenario(system):
        system.start_server(TOKEN=TOKEN)
        system.start_client("e2e-light", "light", TOKEN=TOKEN)
        # the client's own state when it connects
        wait_for(lambda: history(system) == ["client"], "the light's first state")

        system.command("do e2e-light turn_on")
        wait_for(lambda: history(system) == ["client", "console"], "the console's change")

        status, body = system.post("/api/clients/e2e-light/do", {"action": "set_brightness", "params": {"level": 30}}, TOKEN)
        assert status == 200 and body["ok"], body
        assert history(system) == ["client", "console", "dashboard 127.0.0.1"], history(system)

        # asking is not changing
        for _ in range(3):
            system.command("state e2e-light")
        wait_for(lambda: ANSI.sub("", system.log("server")).count("get_state: {") == 3, "three state answers")
        assert len(history(system)) == 3, history(system)

        (stored,) = read_db(system, "SELECT state FROM device_state WHERE client_id = 'e2e-light'")
        assert stored == ('{"brightness": 30, "on": true}',), stored

        # the server stops and starts again: the state and the history are still there
        system.server.terminate()
        system.server.wait(timeout=10)
        system.start_server(TOKEN=TOKEN)
        wait_for(lambda: "3 history entries" in system.log("server"), "the restarted server")
        assert read_db(system, "SELECT state FROM device_state")[0] == stored

    with_system(tmp, scenario)


def test_a_taken_port_is_explained(tmp):
    def scenario(system):
        system.start_server()

        def second_server(name, port, web_port):
            process = system.start(name, SERVER_DIR, {
                "ID": name, "NAME": name, "TYPE": "server", "VERSION": "test",
                "HOST": "127.0.0.1", "PORT": port, "WEB_HOST": "127.0.0.1", "WEB_PORT": web_port,
            }, stdin=subprocess.PIPE)
            # the fatal branch waits for Enter, give it one
            process.stdin.write(b"\n")
            process.stdin.flush()
            process.wait(timeout=30)
            return process.returncode, ANSI.sub("", system.log(name))

        # the ports are checked before the database is opened, so the first server's pyhome.db is untouched
        code, log = second_server("second-web", free_port(), system.web_port)
        assert code != 0 and f"Port {system.web_port} for the dashboard is already in use" in log, log
        assert "Find it with:" in log and "Traceback" not in log, log
        assert "Database" not in log, "a server that cannot start must not open the database"

        code, log = second_server("second-tcp", system.port, free_port())
        assert code != 0 and f"Port {system.port} for the clients is already in use" in log, log
        assert "Database" not in log, "a server that cannot start must not open the database"

    with_system(tmp, scenario)
