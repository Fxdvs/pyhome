"""server/handlers/web_handler.py: running device actions from the dashboard."""
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

from fastapi import HTTPException  # noqa: E402
from shared import config  # noqa: E402
from handlers import client_handler, web_handler  # noqa: E402
from helpers import run_tests  # noqa: E402

LAMP = ("127.0.0.1", 1001)
INDEX = os.path.join(ROOT_DIR, "server", "web", "index.html")


class FakeWriter:
    def __init__(self):
        self.sent = []

    def write(self, data):
        self.sent.append(json.loads(data.decode("utf-8")))

    async def drain(self):
        pass


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": 0, **values}, f)
    config.init(tmp, path)


def add_lamp():
    client_handler.connected_clients.clear()
    client_handler.pending_requests.clear()
    writer = FakeWriter()
    client_handler.connected_clients[LAMP] = {
        "name": "Lamp", "id": "lamp", "writer": writer, "device": "light",
        "capabilities": ["turn_on", "turn_off", "set_brightness"], "last_state": None,
    }
    return writer


async def until(check):
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


def do(client_id, body, answer=None, timeout=2):
    """Run dashboard_do. answer(cmd) is what the fake lamp replies, None for no reply.

    Returns (status, body, printed text).
    """
    writer = client_handler.connected_clients.get(LAMP, {}).get("writer")

    async def scenario():
        task = asyncio.create_task(web_handler.dashboard_do(client_id, body, "192.168.1.30", timeout))
        if answer is not None:
            await until(lambda: writer.sent)
            reply = answer(writer.sent[-1])
            if reply == "disconnect":
                client_handler.fail_pending_requests(LAMP)
            else:
                client_handler.handle_message(LAMP, "lamp", {
                    "type": "result", "request_id": writer.sent[-1]["request_id"], **reply})
        return await task

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status, response = asyncio.run(scenario())
    return status, response, out.getvalue()


def test_device_ran_it(tmp):
    writer = add_lamp()
    status, body, printed = do("lamp", {"action": "set_brightness", "params": {"level": 40}},
                               lambda cmd: {"ok": True, "state": {"on": True, "brightness": 40}})
    assert (status, body) == (200, {"ok": True, "state": {"on": True, "brightness": 40}}), body
    cmd = writer.sent[-1]
    assert cmd["action"] == "set_brightness" and cmd["params"] == {"level": 40}, cmd
    assert client_handler.connected_clients[LAMP]["last_state"] == {"on": True, "brightness": 40}
    assert "Dashboard 192.168.1.30 → Lamp#lamp set_brightness {\"level\": 40}" in printed, printed


def test_params_default_to_nothing(tmp):
    for body in ({"action": "turn_on"}, {"action": "turn_on", "params": None}):
        writer = add_lamp()
        status, _, _ = do("lamp", body, lambda cmd: {"ok": True, "state": {"on": True}})
        assert status == 200 and writer.sent[-1]["params"] == {}, writer.sent[-1]


def test_device_refused_it(tmp):
    add_lamp()
    status, body, _ = do("lamp", {"action": "set_brightness", "params": {"level": 900}},
                         lambda cmd: {"ok": False, "error": "level must be a whole number from 0 to 100"})
    assert (status, body) == (200, {"ok": False, "error": "level must be a whole number from 0 to 100"}), body


def test_bad_bodies(tmp):
    for body, reason in (
        (None, "body must be a JSON object"),
        ([], "body must be a JSON object"),
        ({}, "action must be a non-empty string"),
        ({"action": ""}, "action must be a non-empty string"),
        ({"action": 5}, "action must be a non-empty string"),
        ({"action": "turn_on", "params": []}, "params must be an object"),
        ({"action": "turn_on", "params": {"a": {"b": 1}}}, "params.a must be true, false, a number or text"),
        ({"action": "turn_on", "params": {"a": [1]}}, "params.a must be true, false, a number or text"),
        ({"action": "turn_on", "params": {"a": None}}, "params.a must be true, false, a number or text"),
        ({"action": "turn_on", "params": {"a": float("nan")}}, "params.a must be a finite number"),
    ):
        writer = add_lamp()
        status, answer, printed = do("lamp", body)
        assert (status, answer) == (400, {"error": reason}), (body, answer)
        assert writer.sent == [] and printed == "", body


def test_unknown_action_never_reaches_the_client(tmp):
    writer = add_lamp()
    status, body, _ = do("lamp", {"action": "fly"})
    assert status == 400 and body["error"].startswith("unknown action 'fly'"), body
    assert writer.sent == []


def test_no_such_client(tmp):
    add_lamp()
    status, body, printed = do("nobody", {"action": "turn_on"})
    assert (status, body) == (404, {"error": "no online client with id 'nobody'"}), body
    assert printed == ""


def test_client_disconnected_while_waiting(tmp):
    add_lamp()
    status, body, _ = do("lamp", {"action": "turn_on"}, lambda cmd: "disconnect")
    assert (status, body) == (502, {"error": "client disconnected"}), body
    assert client_handler.pending_requests == {}


def test_no_answer_in_time(tmp):
    add_lamp()
    status, body, _ = do("lamp", {"action": "turn_on"}, timeout=0.05)
    assert (status, body) == (504, {"error": "no answer within 0.05 s"}), body
    assert client_handler.pending_requests == {}


def test_timeout_message_with_the_default(tmp):
    # the default is a whole number of seconds and must read like one
    assert web_handler.dashboard_do.__defaults__ == (client_handler.COMMAND_TIMEOUT,)
    assert f"{client_handler.COMMAND_TIMEOUT:g}" == "5"


def test_controls_need_a_server_token(tmp):
    use_server_config(tmp, TOKEN="")
    try:
        asyncio.run(web_handler.require_controls())
    except HTTPException as e:
        assert e.status_code == 403 and "set TOKEN" in e.detail, (e.status_code, e.detail)
    else:
        raise AssertionError("controls must be refused without a server token")
    use_server_config(tmp, TOKEN="s3cret")
    assert asyncio.run(web_handler.require_controls()) is None


def test_the_do_route_checks_token_then_controls(tmp):
    route = next(r for r in web_handler.app.routes if getattr(r, "path", "") == "/api/clients/{client_id}/do")
    assert route.methods == {"POST"}, route.methods
    assert [d.dependency for d in route.dependencies] == [web_handler.require_token, web_handler.require_controls]


def read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def test_page_posts_actions_with_the_token(tmp):
    page = read_index()
    assert '"/api/clients/" + encodeURIComponent(id) + "/do"' in page
    assert 'method: "POST"' in page
    assert 'headers: { ...authHeaders(), "Content-Type": "application/json" }' in page


def test_page_controls_only_when_the_server_allows(tmp):
    page = read_index()
    assert "controls = !!status.controls;" in page
    # demo data and a failed status read never get controls
    assert page.count("controls = false;") >= 1
    assert "return controls && (c.capabilities || []).includes(action);" in page


def test_page_sends_the_slider_once_on_release(tmp):
    page = read_index()
    assert 'clientsGrid.addEventListener("change"' in page
    # input only moves the fill, it never sends anything
    start = page.index('clientsGrid.addEventListener("input"')
    end = page.index("});", start)
    assert "runAction" not in page[start:end], page[start:end]


def test_page_does_not_redraw_a_busy_card(tmp):
    page = read_index()
    assert "fresh.dataset.id = id;" in page
    assert "const busy = pending.has(id) || dragging.has(id);" in page
    # the old way replaced the whole grid on every poll
    assert "clients.map(clientCard).join" not in page


def test_page_shows_errors_for_a_while(tmp):
    page = read_index()
    assert "until: Date.now() + 4000" in page
    assert 'class="err"' in page


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
