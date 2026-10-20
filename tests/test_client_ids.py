"""Addressing clients from the console: an exact id, or the start of one."""
import asyncio
import contextlib
import io
import json
import os
import re
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from handlers import client_handler  # noqa: E402
from handlers.devices import run_and_print  # noqa: E402
from helpers import run_tests  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")


class FakeWriter:
    def __init__(self):
        self.sent = []

    def write(self, data):
        self.sent.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


def online(*ids):
    """Fake online clients with these ids, each a light. Returns {id: writer}."""
    client_handler.connected_clients.clear()
    client_handler.pending_requests.clear()
    writers = {}
    for port, client_id in enumerate(ids, 2000):
        writers[client_id] = FakeWriter()
        client_handler.connected_clients[("127.0.0.1", port)] = {
            "name": str(client_id).title(), "id": client_id, "writer": writers[client_id],
            "device": "light", "capabilities": ["turn_on"], "last_state": None,
        }
    return writers


def found(target):
    return client_handler.find_online_client(target)[1]["id"]


def refused(target):
    try:
        client_handler.find_online_client(target)
    except LookupError as e:
        return str(e)
    raise AssertionError(f"'{target}' should have been refused")


def test_exact_id(tmp):
    online("kuchyna-svetlo", "obyvacka-termostat")
    assert found("kuchyna-svetlo") == "kuchyna-svetlo"
    assert found("obyvacka-termostat") == "obyvacka-termostat"


def test_unique_prefix(tmp):
    online("kuchyna-svetlo", "obyvacka-termostat")
    for target in ("kuch", "k", "kuchyna-", "KUCH", "Kuchyna-Svetlo"):
        assert found(target) == "kuchyna-svetlo", target
    assert found("o") == "obyvacka-termostat"


def test_ambiguous_prefix_lists_every_match(tmp):
    online("kuchyna-termostat", "kuchyna-svetlo", "obyvacka-termostat")
    assert refused("kuch") == "'kuch' matches 2 online clients: kuchyna-svetlo, kuchyna-termostat"
    # a longer prefix settles it
    assert found("kuchyna-s") == "kuchyna-svetlo"


def test_exact_id_wins_over_a_longer_one_it_starts(tmp):
    online("kuchyna", "kuchyna-svetlo")
    assert found("kuchyna") == "kuchyna"
    assert found("KUCHYNA") == "kuchyna"
    assert found("kuchyna-") == "kuchyna-svetlo"


def test_case_only_twins_need_the_exact_id(tmp):
    online("Lamp", "lamp")
    assert found("Lamp") == "Lamp" and found("lamp") == "lamp"
    assert refused("LAMP") == "'LAMP' matches 2 online clients: Lamp, lamp"


def test_nothing_matches(tmp):
    online("kuchyna-svetlo")
    assert refused("spalna") == "no online client with id 'spalna'"
    online()
    assert refused("k") == "no online client with id 'k'"


def test_only_online_clients_count(tmp):
    # the server only keeps online clients here, an offline twin is simply not in the list
    online("kuchyna-svetlo")
    assert found("kuch") == "kuchyna-svetlo"


def test_numeric_ids(tmp):
    online("1", "12", 3)
    assert found("1") == "1"
    assert found("12") == "12"
    assert found("3") == 3


def test_send_command_takes_a_prefix(tmp):
    writers = online("kuchyna-svetlo", "obyvacka-termostat")
    try:
        asyncio.run(client_handler.send_command("kuch", "turn_on", {}, timeout=0.05))
    except asyncio.TimeoutError:
        pass
    assert len(writers["kuchyna-svetlo"].sent) == 1 and writers["obyvacka-termostat"].sent == []


def test_send_to_clients_takes_a_prefix(tmp):
    writers = online("kuchyna-svetlo", "obyvacka-termostat")
    delivered, failed = asyncio.run(client_handler.send_to_clients("obyv", "ahoj"))
    assert delivered == ["Obyvacka-Termostat#obyvacka-termostat"] and failed == [], (delivered, failed)
    assert writers["kuchyna-svetlo"].sent == []


def test_send_all_still_reaches_everyone(tmp):
    writers = online("kuchyna-svetlo", "obyvacka-termostat")
    delivered, _ = asyncio.run(client_handler.send_to_clients("all", "ahoj"))
    assert len(delivered) == 2
    assert all(w.sent[-1]["text"] == "ahoj" for w in writers.values())


def test_send_to_an_ambiguous_prefix_sends_nothing(tmp):
    writers = online("kuchyna-svetlo", "kuchyna-termostat")
    try:
        asyncio.run(client_handler.send_to_clients("kuch", "ahoj"))
    except LookupError as e:
        assert "matches 2 online clients" in str(e), e
    else:
        raise AssertionError("expected LookupError")
    assert all(w.sent == [] for w in writers.values())


def test_do_prints_the_full_id(tmp):
    writers = online("kuchyna-svetlo", "obyvacka-termostat")

    async def scenario():
        task = asyncio.create_task(run_and_print("kuch", "turn_on", {}))
        for _ in range(100):
            if writers["kuchyna-svetlo"].sent:
                break
            await asyncio.sleep(0)
        cmd = writers["kuchyna-svetlo"].sent[-1]
        addr = next(a for a, i in client_handler.connected_clients.items() if i["id"] == "kuchyna-svetlo")
        client_handler.handle_message(addr, "x", {"type": "result", "request_id": cmd["request_id"],
                                                 "ok": True, "state": {"on": True}})
        await task

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        asyncio.run(scenario())
    assert 'kuchyna-svetlo turn_on: {"on": true}' in ANSI.sub("", out.getvalue()), out.getvalue()


def test_do_prints_why_a_prefix_is_ambiguous(tmp):
    online("kuchyna-svetlo", "kuchyna-termostat")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        asyncio.run(run_and_print("kuch", "turn_on", {}))
    assert "'kuch' matches 2 online clients: kuchyna-svetlo, kuchyna-termostat" in out.getvalue(), out.getvalue()


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
