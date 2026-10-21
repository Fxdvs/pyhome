"""End to end: v1.3 Part 3 "Done when", what a real server remembers, on the dashboard and the console."""
import contextlib
import glob
import os
import re
import sqlite3
import sys
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402

TOKEN = "s3cret-offline"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_offline_devices_history_backup_and_clear(tmp):
    def scenario(system):
        def server_log():
            return ANSI.sub("", system.log("server"))

        system.start_server(TOKEN=TOKEN)
        system.start_client("e2e-light", "light", TOKEN=TOKEN)
        thermo = system.start("e2e-thermo", os.path.join(os.path.dirname(TESTS_DIR), "client"), {
            "ID": "e2e-thermo", "NAME": "E2e-Thermo", "TYPE": "client", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": system.port, "DEVICE": "thermostat", "TOKEN": TOKEN,
        })
        wait_for(lambda: system.client("e2e-light") and system.client("e2e-thermo"), "both clients")
        status, _ = system.post("/api/clients/e2e-thermo/do", {"action": "set_target", "params": {"temperature": 23}}, TOKEN)
        assert status == 200

        # the thermostat goes away, the server still knows it and how it was
        thermo.terminate()
        thermo.wait(timeout=10)
        wait_for(lambda: system.known("e2e-thermo") and not system.known("e2e-thermo")["online"], "the thermostat offline")
        clients = system.api()
        assert [(c["id"], c["online"]) for c in clients] == [("e2e-light", True), ("e2e-thermo", False)], clients
        offline = clients[1]
        assert offline["last_state"]["target"] == 23.0 and offline["host"] is None and offline["last_seen"], offline
        # controls go only to online clients
        assert system.post("/api/clients/e2e-thermo/do", {"action": "turn_on"}, TOKEN)[0] == 404

        # its history over the API, newest first
        status, body = system.http("/api/clients/e2e-thermo/history?limit=1", TOKEN)
        assert status == 200 and body["history"][0]["source"] == "dashboard 127.0.0.1", body
        assert system.http("/api/clients/e2e-thermo/history")[0] == 401

        # and on the console, an offline client by its full id
        system.command("history e2e-thermo")
        wait_for(lambda: "History of e2e-thermo, newest first:" in server_log(), "the console history")
        system.command("list")
        wait_for(lambda: "E2e-Thermo#e2e-thermo thermostat, last seen" in server_log(), "list with the offline client")

        # a backup while the server runs
        system.command("data backup")
        wait_for(lambda: glob.glob(os.path.join(system.tmp, "pyhome-backup-*.db")), "the backup file")
        (backup,) = glob.glob(os.path.join(system.tmp, "pyhome-backup-*.db"))
        wait_for(lambda: "Backup written to" in server_log(), "the backup line")
        with contextlib.closing(sqlite3.connect(backup)) as db:
            assert sorted(r[0] for r in db.execute("SELECT id FROM clients")) == ["e2e-light", "e2e-thermo"]

        # while clear waits for y or n the server keeps answering
        system.command("data clients clear")
        wait_for(lambda: "Are you sure you want to clear the client list" in server_log(), "the question")
        time.sleep(0.5)
        assert system.http("/api/status")[0] == 200, "the dashboard must answer while the console waits"
        system.command("y")
        wait_for(lambda: "List of clients has been cleared, 1 connected kept." in server_log(), "the clear")
        # a client still connected stays known, and keeps working
        assert system.known_ids() == ["e2e-light"], system.known_ids()
        status, body = system.post("/api/clients/e2e-light/do", {"action": "turn_on"}, TOKEN)
        assert status == 200 and body["ok"], body
        assert system.client("e2e-light"), "the light must still be connected"
        assert "had a fatal error" not in server_log(), server_log()

    with_system(tmp, scenario)
