"""v1.3 Part 2: the last state across restarts, the history of changes and where each came from."""
import asyncio
import contextlib
import datetime
import io
import json
import os
import socket
import sqlite3
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config, network  # noqa: E402
from shared.protocol import read_message, send_message  # noqa: E402
from handlers import client_handler, store, web_handler  # noqa: E402

pytestmark = pytest.mark.usefixtures("store_db")

LAMP = ("127.0.0.1", 3001)


class FakeWriter:
    def __init__(self):
        self.sent = []

    def write(self, data):
        self.sent.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


def add_lamp():
    client_handler.connected_clients.clear()
    client_handler.pending_requests.clear()
    writer = FakeWriter()
    client_handler.connected_clients[LAMP] = {
        "name": "Lamp", "id": "lamp", "writer": writer, "device": "light",
        "capabilities": ["turn_on", "turn_off"], "last_state": None,
    }
    store.upsert_client("lamp", "Lamp", "light", ["turn_on", "turn_off"])
    return writer


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": 0, **values}, f)
    config.init(tmp, path)


def sources():
    return [entry["source"] for entry in store.get_history("lamp")]


def quietly(coroutine):
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(coroutine)


async def answer_next_cmd(writer, state, ok=True):
    """Wait for the next cmd the fake lamp receives and answer it with state."""
    for _ in range(100):
        if writer.sent:
            break
        await asyncio.sleep(0)
    cmd = writer.sent.pop()
    client_handler.handle_message(LAMP, "lamp", {"type": "result", "request_id": cmd["request_id"],
                                                 "ok": ok, "state": state})


# the store

def test_save_state_records_only_changes(tmp):
    store.upsert_client("lamp", "Lamp", "light", [])
    assert store.get_state("lamp") is None
    assert store.save_state("lamp", {"on": True, "brightness": 40}, "client") is True
    assert store.save_state("lamp", {"on": True, "brightness": 40}, "console") is False
    # the same state in another key order is the same state
    assert store.save_state("lamp", {"brightness": 40, "on": True}, "console") is False
    assert store.save_state("lamp", {"on": False, "brightness": 40}, "console") is True
    assert store.get_state("lamp") == {"on": False, "brightness": 40}
    assert store.count_history() == 2
    assert [e["state"]["on"] for e in store.get_history("lamp")] == [False, True], "newest first"
    assert sources() == ["console", "client"]


def test_history_limit_and_other_clients(tmp):
    store.upsert_client("lamp", "Lamp", "light", [])
    store.upsert_client("heater", "Heater", "thermostat", [])
    for level in range(5):
        store.save_state("lamp", {"level": level}, "console")
    store.save_state("heater", {"target": 21}, "client")
    assert [e["state"]["level"] for e in store.get_history("lamp", limit=3)] == [4, 3, 2]
    assert len(store.get_history("heater")) == 1
    assert store.get_history("nobody") == []


def test_prune_history(tmp):
    store.upsert_client("lamp", "Lamp", "light", [])
    with sqlite3.connect(os.path.join(tmp, "pyhome.db")) as db:
        for at in ("2026-01-01T00:00:00Z", "2026-06-30T23:59:59Z", "2026-07-02T00:00:00Z", "2026-09-29T12:00:00Z"):
            db.execute("INSERT INTO state_history (client_id, at, state, source) VALUES ('lamp', ?, '{}', 'client')", (at,))
    now = datetime.datetime(2026, 9, 30, 12, 0, tzinfo=datetime.timezone.utc)
    # 90 days before now is 2026-07-02T12:00:00Z
    assert store.prune_history(90, now=now) == 3
    assert [e["at"] for e in store.get_history("lamp")] == ["2026-09-29T12:00:00Z"]
    assert store.prune_history(0) == 1
    assert store.count_history() == 0


def test_history_days_from_the_config(tmp):
    for values, expected in (({}, 90), ({"HISTORY_DAYS": 30}, 30), ({"HISTORY_DAYS": "14"}, 14),
                             ({"HISTORY_DAYS": -5}, 0), ({"HISTORY_DAYS": "a lot"}, 90), ({"HISTORY_DAYS": None}, 90)):
        use_server_config(tmp, **values)
        assert store.history_days() == expected, values


# where a change came from

def test_unprompted_state_is_the_clients(tmp):
    add_lamp()
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(LAMP, "lamp", {"type": "state", "state": {"on": True}})
        # the same state again, after a reconnect for example, adds nothing
        client_handler.handle_message(LAMP, "lamp", {"type": "state", "state": {"on": True}})
    assert sources() == ["client"]
    assert client_handler.connected_clients[LAMP]["last_state"] == {"on": True}


def test_console_is_the_default_source(tmp):
    writer = add_lamp()

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "turn_on", {}, timeout=2))
        await answer_next_cmd(writer, {"on": True})
        await task

    quietly(scenario())
    assert sources() == ["console"]


def test_dashboard_records_its_address(tmp):
    writer = add_lamp()

    async def scenario():
        task = asyncio.create_task(web_handler.dashboard_do("lamp", {"action": "turn_on"}, "192.168.1.30", 2))
        await answer_next_cmd(writer, {"on": True})
        return await task

    status, body = quietly(scenario())
    assert status == 200 and body["ok"] is True, body
    assert sources() == ["dashboard 192.168.1.30"]


def test_refused_result_records_nothing(tmp):
    writer = add_lamp()

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "turn_on", {}, timeout=2))
        await answer_next_cmd(writer, None, ok=False)
        await task

    quietly(scenario())
    assert store.count_history() == 0


def test_late_result_is_the_clients(tmp):
    add_lamp()
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(LAMP, "lamp", {"type": "result", "request_id": "gone1234",
                                                     "ok": True, "state": {"on": False}})
    assert sources() == ["client"]


def test_reconnecting_client_starts_from_the_stored_state(tmp):
    use_server_config(tmp)
    store.upsert_client("lamp", "Lamp", "light", [])
    store.save_state("lamp", {"on": True, "brightness": 40}, "console")
    client_handler.connected_clients.clear()

    async def scenario():
        server = await asyncio.start_server(client_handler.handle_client_async, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            await send_message(writer, "hello", id="lamp", name="Lamp", role="client", version="test",
                               device="light", capabilities=["turn_on"], token=None)
            await read_message(reader)
            # before the client says anything about its state
            return [info["last_state"] for info in client_handler.connected_clients.values()]
        finally:
            writer.close()
            server.close()

    assert quietly(scenario()) == [{"on": True, "brightness": 40}]


# a port that is taken

def test_address_in_use_is_recognised(tmp):
    import errno
    assert network.is_address_in_use(OSError(errno.EADDRINUSE, "in use"))
    assert network.is_address_in_use(OSError(10048, "only one usage of each socket address"))
    assert not network.is_address_in_use(OSError(errno.ECONNREFUSED, "refused"))
    assert not network.is_address_in_use(ValueError("not an OSError"))


def test_port_in_use_message(tmp, monkeypatch):
    monkeypatch.setattr(network.os, "name", "nt")
    assert network.port_in_use_message(50000, "clients") == (
        "Port 50000 for the clients is already in use, probably by another pyhome server.\n"
        "  Find it with: netstat -ano | findstr :50000")
    monkeypatch.setattr(network.os, "name", "posix")
    assert network.port_in_use_message(50001, "dashboard").endswith("Find it with: lsof -i :50001")


def test_check_port_free(tmp):
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(OSError) as error:
            network.check_port_free("127.0.0.1", port)
        assert network.is_address_in_use(error.value), error.value
    # free again once the listener is gone
    network.check_port_free("127.0.0.1", port)
