"""Server side of device commands: params, request matching, state, clients file."""
import asyncio
import contextlib
import io
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from handlers import client_handler  # noqa: E402
from handlers.devices import parse_params, parse_value  # noqa: E402
from helpers import run_tests  # noqa: E402

LAMP = ("127.0.0.1", 1001)
HEATER = ("127.0.0.1", 1002)


class FakeWriter:
    def __init__(self):
        self.sent = []

    def write(self, data):
        self.sent.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


def add_client(addr, client_id):
    writer = FakeWriter()
    client_handler.connected_clients[addr] = {
        "name": client_id.title(), "id": client_id, "writer": writer,
        "device": "light", "capabilities": ["turn_on"], "last_state": None,
    }
    return writer


def reset():
    client_handler.connected_clients.clear()
    client_handler.pending_requests.clear()


def quietly(coroutine):
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(coroutine)


async def until(check):
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


def test_parse_value(tmp):
    assert parse_value("40") == 40 and isinstance(parse_value("40"), int)
    assert parse_value("-3") == -3
    assert parse_value("21.5") == 21.5
    assert parse_value("true") is True and parse_value("False") is False
    assert parse_value("warm") == "warm"
    # inf and nan are floats to python but not numbers anyone meant
    assert parse_value("inf") == "inf" and parse_value("nan") == "nan"


def test_parse_params(tmp):
    assert parse_params([]) == {}
    assert parse_params(["level=40", "on=true", "mode=eco", "t=21.5"]) == {
        "level": 40, "on": True, "mode": "eco", "t": 21.5}
    assert parse_params(["note="]) == {"note": ""}
    for bad in (["level"], ["=40"]):
        try:
            parse_params(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_clean_capabilities(tmp):
    assert client_handler.clean_capabilities(["a", "b"]) == ["a", "b"]
    assert client_handler.clean_capabilities(["a", 1, None]) == ["a"]
    assert client_handler.clean_capabilities(None) == []
    assert client_handler.clean_capabilities("turn_on") == []


def test_result_completes_the_command(tmp):
    reset()
    writer = add_client(LAMP, "lamp")

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "set_brightness", {"level": 40}, timeout=2))
        await until(lambda: writer.sent)
        cmd = writer.sent[-1]
        assert cmd["type"] == "cmd" and cmd["action"] == "set_brightness" and cmd["params"] == {"level": 40}, cmd
        assert isinstance(cmd["request_id"], str) and len(cmd["request_id"]) == 8, cmd
        client_handler.handle_message(LAMP, "lamp", {
            "type": "result", "request_id": cmd["request_id"], "ok": True, "state": {"brightness": 40}})
        return await task

    result = quietly(scenario())
    assert result["ok"] is True and result["state"] == {"brightness": 40}, result
    assert client_handler.connected_clients[LAMP]["last_state"] == {"brightness": 40}
    assert client_handler.pending_requests == {}


def test_failed_result_keeps_last_state(tmp):
    reset()
    writer = add_client(LAMP, "lamp")
    client_handler.connected_clients[LAMP]["last_state"] = {"on": True}

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "fly", {}, timeout=2))
        await until(lambda: writer.sent)
        client_handler.handle_message(LAMP, "lamp", {
            "type": "result", "request_id": writer.sent[-1]["request_id"], "ok": False, "error": "unknown action 'fly'"})
        return await task

    result = quietly(scenario())
    assert result == {"type": "result", "request_id": result["request_id"], "ok": False, "error": "unknown action 'fly'"}
    assert client_handler.connected_clients[LAMP]["last_state"] == {"on": True}


def test_result_from_another_client_is_ignored(tmp):
    reset()
    writer = add_client(LAMP, "lamp")
    add_client(HEATER, "heater")

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "turn_on", {}, timeout=0.2))
        await until(lambda: writer.sent)
        client_handler.handle_message(HEATER, "heater", {
            "type": "result", "request_id": writer.sent[-1]["request_id"], "ok": True, "state": {}})
        await task

    try:
        quietly(scenario())
    except asyncio.TimeoutError:
        assert client_handler.pending_requests == {}
        return
    raise AssertionError("a result from the wrong client must not complete the request")


def test_command_reaches_only_its_client(tmp):
    reset()
    lamp = add_client(LAMP, "lamp")
    heater = add_client(HEATER, "heater")

    async def scenario():
        try:
            await client_handler.send_command("lamp", "turn_on", {}, timeout=0.05)
        except asyncio.TimeoutError:
            pass

    quietly(scenario())
    assert len(lamp.sent) == 1 and heater.sent == []


def test_unknown_client_raises_lookup_error(tmp):
    reset()
    try:
        quietly(client_handler.send_command("nobody", "turn_on", {}, timeout=0.1))
    except LookupError:
        return
    raise AssertionError("expected LookupError")


def test_timeout_cleans_up(tmp):
    reset()
    add_client(LAMP, "lamp")
    try:
        quietly(client_handler.send_command("lamp", "turn_on", {}, timeout=0.05))
    except asyncio.TimeoutError:
        assert client_handler.pending_requests == {}
        return
    raise AssertionError("expected TimeoutError")


def test_disconnect_fails_waiting_commands(tmp):
    reset()
    writer = add_client(LAMP, "lamp")

    async def scenario():
        task = asyncio.create_task(client_handler.send_command("lamp", "turn_on", {}, timeout=2))
        await until(lambda: writer.sent)
        client_handler.fail_pending_requests(LAMP)
        await task

    try:
        quietly(scenario())
    except ConnectionError:
        assert client_handler.pending_requests == {}
        return
    raise AssertionError("expected ConnectionError")


def test_late_result_is_harmless(tmp):
    reset()
    add_client(LAMP, "lamp")
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(LAMP, "lamp", {"type": "result", "request_id": "gone1234", "ok": True, "state": {"on": False}})
    assert client_handler.connected_clients[LAMP]["last_state"] == {"on": False}


def test_state_message_updates_last_state(tmp):
    reset()
    add_client(LAMP, "lamp")
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(LAMP, "lamp", {"type": "state", "state": {"on": True, "brightness": 5}})
        client_handler.handle_message(LAMP, "lamp", {"type": "state", "state": "garbage"})
    assert client_handler.connected_clients[LAMP]["last_state"] == {"on": True, "brightness": 5}


def test_unknown_type_is_ignored(tmp):
    reset()
    add_client(LAMP, "lamp")
    with contextlib.redirect_stdout(io.StringIO()):
        client_handler.handle_message(LAMP, "lamp", {"type": "bogus"})
    assert LAMP in client_handler.connected_clients


def test_clients_file_sits_next_to_the_config(tmp):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s"}, f)
    config.init(tmp, path)
    assert client_handler.get_clients_file() == os.path.join(tmp, "clients.json")


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
