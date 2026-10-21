"""End to end: v1.3 Part 1 "Done when", the database of a real server across a restart."""
import json
import os
import sqlite3
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402


def test_clients_are_remembered_across_a_restart(tmp):
    def scenario(system):
        # an old server's list, which the first start imports and renames
        with open(os.path.join(system.tmp, "clients.json"), "w", encoding="utf-8") as f:
            json.dump([{"ID": "old-lamp", "NAME": "Old lamp"}], f)

        system.start_server()
        assert "Database " in system.log("server") and "1 imported from clients.json" in system.log("server")
        assert not os.path.exists(os.path.join(system.tmp, "clients.json"))
        assert os.path.exists(os.path.join(system.tmp, "clients.json.imported"))

        system.start_client("e2e-light", "light")
        wait_for(lambda: system.client("e2e-light"), "the light")
        assert system.known_ids() == ["e2e-light", "old-lamp"], system.known_ids()

        # stop the server and start it again on the same folder
        system.server.terminate()
        system.server.wait(timeout=10)
        system.start_server()
        wait_for(lambda: "2 clients known" in system.log("server"), "the restarted server")
        assert "imported" not in system.log("server"), "the import runs once"

        uri = "file:" + os.path.join(system.tmp, "pyhome.db").replace("\\", "/") + "?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        try:
            device, capabilities = db.execute(
                "SELECT device, capabilities FROM clients WHERE id = 'e2e-light'").fetchone()
            assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        finally:
            db.close()
        assert device == "light" and json.loads(capabilities) == ["turn_on", "turn_off", "set_brightness"]

    with_system(tmp, scenario)


def test_a_newer_database_stops_the_server(tmp):
    def scenario(system):
        db = sqlite3.connect(os.path.join(system.tmp, "pyhome.db"))
        db.execute("PRAGMA user_version = 99")
        db.close()
        process = system.start("server", os.path.join(os.path.dirname(TESTS_DIR), "server"), {
            "ID": "e2e-server", "NAME": "E2E server", "TYPE": "server", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": system.port, "WEB_HOST": "127.0.0.1", "WEB_PORT": system.web_port,
        }, stdin=__import__("subprocess").PIPE)
        process.stdin.write(b"\n")
        process.stdin.flush()
        process.wait(timeout=30)
        assert process.returncode != 0
        assert "pyhome.db is version 99, this server knows up to 1" in system.log("server"), system.log("server")

    with_system(tmp, scenario)
