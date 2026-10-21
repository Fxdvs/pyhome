"""v1.3 Part 3 on the console: list, history, data backup, and questions that do not stop the server."""
import asyncio
import builtins
import contextlib
import io
import json
import os
import re
import sqlite3
import sys
import threading

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from handlers import client_handler  # noqa: E402
from handlers.commands import data_backup, data_clients_clear, data_config_edit_name, history, list as list_command  # noqa: E402

pytestmark = pytest.mark.usefixtures("store_db")

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run(coroutine):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        asyncio.run(coroutine)
    return ANSI.sub("", out.getvalue())


def two_lamps(store):
    """kuchyna-svetlo online, spalna-svetlo known but offline, with a history."""
    client_handler.connected_clients.clear()
    for client_id in ("kuchyna-svetlo", "spalna-svetlo"):
        store.upsert_client(client_id, client_id.title(), "light", ["turn_on"])
    client_handler.connected_clients[("127.0.0.1", 4001)] = {
        "writer": None, "id": "kuchyna-svetlo", "name": "Kuchyna-Svetlo", "device": "light",
        "capabilities": ["turn_on"], "last_state": None,
    }
    store.save_state("kuchyna-svetlo", {"on": True}, "console")
    store.save_state("kuchyna-svetlo", {"on": False}, "dashboard 192.168.1.30")
    store.save_state("spalna-svetlo", {"on": True}, "client")


def test_list_shows_online_and_offline(tmp, store_db):
    two_lamps(store_db)
    seen = store_db.local_time(store_db.get_client("spalna-svetlo")["last_seen"])
    out = run(list_command.function())
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("#")]
    assert lines == ["#1 Kuchyna-Svetlo#kuchyna-svetlo (127.0.0.1:4001) light",
                     f"#2 Spalna-Svetlo#spalna-svetlo light, last seen {seen}"], lines


def test_history_by_prefix_newest_first(tmp, store_db):
    two_lamps(store_db)
    out = run(history.function("kuch"))
    assert "History of kuchyna-svetlo, newest first:" in out
    body = [line for line in out.splitlines() if line.startswith("  ")]
    assert len(body) == 2
    assert "dashboard 192.168.1.30" in body[0] and '{"on": false}' in body[0], body
    assert "console" in body[1] and '{"on": true}' in body[1], body


def test_history_of_an_offline_client_by_its_full_id(tmp, store_db):
    two_lamps(store_db)
    assert "History of spalna-svetlo" in run(history.function("spalna-svetlo"))
    # a prefix only reaches online clients, as for do
    assert "no online client with id 'spal'" in run(history.function("spal"))


def test_history_count_and_errors(tmp, store_db):
    two_lamps(store_db)
    out = run(history.function("kuchyna-svetlo", "1"))
    assert len([line for line in out.splitlines() if line.startswith("  ")]) == 1
    assert "count must be a whole number above 0, got 'zero'" in run(history.function("kuchyna-svetlo", "zero"))
    assert "count must be a whole number above 0, got '0'" in run(history.function("kuchyna-svetlo", "0"))
    assert "Usage: history" in run(history.function())
    store_db.upsert_client("quiet", "Quiet", None, [])
    assert "No history for quiet" in run(history.function("quiet"))


def test_backup_is_a_consistent_copy(tmp, store_db):
    two_lamps(store_db)
    out = run(data_backup.function())
    (path,) = re.findall(r"Backup written to (.+)", out)
    path = path.strip()
    assert os.path.dirname(path) == tmp and re.fullmatch(r"pyhome-backup-\d{4}-\d{2}-\d{2}-\d{6}\.db", os.path.basename(path))
    # the copy has everything, also what still waits in the WAL file of the live database
    with contextlib.closing(sqlite3.connect(path)) as db:
        assert sorted(r[0] for r in db.execute("SELECT id FROM clients")) == ["kuchyna-svetlo", "spalna-svetlo"]
        assert db.execute("SELECT COUNT(*) FROM state_history").fetchone()[0] == 3
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def answered_later(monkeypatch, answers):
    """Make input() wait until released, like a person thinking. Returns the release event."""
    release = threading.Event()
    queue = list(answers)

    def slow_input(prompt=""):
        release.wait(5)
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", slow_input)
    return release


def loop_keeps_running(command, release):
    """Run command while counting event loop ticks; release input() after a while. Returns the ticks seen."""
    ticks = []

    async def scenario():
        async def ticker():
            while True:
                ticks.append(1)
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        asyncio.get_running_loop().call_later(0.3, release.set)
        await command
        task.cancel()

    run(scenario())
    return len(ticks)


def test_clear_does_not_stop_the_server_while_it_asks(tmp, store_db, monkeypatch):
    two_lamps(store_db)
    release = answered_later(monkeypatch, ["y"])
    ticks = loop_keeps_running(data_clients_clear.function(), release)
    # about 30 ticks in 0.3 s; an input() on the loop would have allowed one at most
    assert ticks >= 10, ticks
    assert [c["id"] for c in store_db.list_clients()] == ["kuchyna-svetlo"] and store_db.count_history() == 0


def test_clear_keeps_connected_clients_known(tmp, store_db, monkeypatch):
    two_lamps(store_db)
    release = answered_later(monkeypatch, ["y"])
    release.set()
    out = run(data_clients_clear.function())
    assert "List of clients has been cleared, 1 connected kept." in out, out
    assert [c["id"] for c in store_db.list_clients()] == ["kuchyna-svetlo"]
    # its history went with the clear, and its next state is stored without an error
    assert store_db.count_history() == 0
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(("127.0.0.1", 4001), "k", {"type": "state", "state": {"on": True}})
    assert store_db.count_history() == 1


def test_clear_cancelled(tmp, store_db, monkeypatch):
    two_lamps(store_db)
    release = answered_later(monkeypatch, ["n"])
    release.set()
    assert "Operation cancelled." in run(data_clients_clear.function())
    assert store_db.count_clients() == 2


def test_edit_name_does_not_stop_the_server_while_it_asks(tmp, monkeypatch):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test"}, f)
    config.init(tmp, path)
    monkeypatch.setattr(os, "system", lambda command: 0)
    release = answered_later(monkeypatch, ["y", "Dom", "y"])
    ticks = loop_keeps_running(data_config_edit_name.function(), release)
    assert ticks >= 10, ticks
    assert config.get_config("NAME") == "Dom"
