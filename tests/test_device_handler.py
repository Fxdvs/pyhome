"""client/handlers/device_handler.py and the devices in client/devices."""
import asyncio
import contextlib
import io
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
CLIENT_DIR = os.path.join(ROOT_DIR, "client")
DEVICES_DIR = os.path.join(CLIENT_DIR, "devices")
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, CLIENT_DIR)
sys.path.insert(0, ROOT_DIR)

from handlers import device_handler  # noqa: E402
from helpers import run_tests  # noqa: E402


def run(coroutine):
    # devices print through print_message, keep the test output clean
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(coroutine)


def load(name):
    return device_handler.load_device(DEVICES_DIR, "devices", name)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_no_device_loads_nothing(tmp):
    assert load("") is None
    assert load(None) is None
    assert device_handler.get_device() is None
    assert device_handler.get_capabilities() == []


def test_no_device_rejects_actions(tmp):
    load("")
    reply = run(device_handler.execute("turn_on", {}))
    assert reply["ok"] is False and "no device" in reply["error"], reply


def test_light_capabilities(tmp):
    module = load("light")
    assert device_handler.get_device() is module
    assert module.device == "light"
    assert device_handler.get_capabilities() == ["turn_on", "turn_off", "set_brightness"]


def test_thermostat_capabilities(tmp):
    load("thermostat")
    assert device_handler.get_capabilities() == ["turn_on", "turn_off", "set_target"]


def test_light_actions_change_state(tmp):
    load("light")
    run(device_handler.run_action("turn_off", {}))
    reply = run(device_handler.execute("set_brightness", {"level": 40}))
    assert reply == {"ok": True, "state": {"on": False, "brightness": 40}}, reply
    reply = run(device_handler.execute("turn_on", {}))
    assert reply == {"ok": True, "state": {"on": True, "brightness": 40}}, reply


def test_get_state_is_always_available(tmp):
    load("light")
    run(device_handler.run_action("set_brightness", {"level": 70}))
    state = run(device_handler.run_action("get_state", {}))
    assert state["brightness"] == 70, state
    reply = run(device_handler.execute("get_state", {}))
    assert reply["ok"] is True and reply["state"]["brightness"] == 70, reply


def test_unknown_action_fails_cleanly(tmp):
    load("thermostat")
    reply = run(device_handler.execute("set_brightness", {"level": 40}))
    assert reply == {"ok": False, "error": "unknown action 'set_brightness'"}, reply


def test_bad_value_fails_cleanly(tmp):
    load("light")
    for level in (101, -1, "bright", True, 40.5):
        reply = run(device_handler.execute("set_brightness", {"level": level}))
        assert reply["ok"] is False and "0 to 100" in reply["error"], (level, reply)


def test_params_must_be_an_object(tmp):
    load("light")
    reply = run(device_handler.execute("turn_on", ["level", 1]))
    assert reply["ok"] is False and "params" in reply["error"], reply


def test_thermostat_heats_below_target(tmp):
    load("thermostat")
    run(device_handler.run_action("turn_on", {}))
    reply = run(device_handler.execute("set_target", {"temperature": 25}))
    assert reply["ok"] is True, reply
    state = reply["state"]
    assert state["on"] is True and state["target"] == 25.0 and state["heating"] is True, state
    reply = run(device_handler.execute("set_target", {"temperature": 18}))
    assert reply["state"]["heating"] is False, reply
    reply = run(device_handler.execute("set_target", {"temperature": 99}))
    assert reply["ok"] is False and "5 to 30" in reply["error"], reply


def test_missing_device_raises(tmp):
    for name in ("toaster", "../light", "light.sub"):
        try:
            load(name)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {name!r}")
    assert device_handler.get_device() is None


def test_device_breaking_the_contract_raises(tmp):
    # a package of our own next to the real devices would be picked up by the app, use tmp
    devices = os.path.join(tmp, "contract_devices")
    write(os.path.join(devices, "__init__.py"), "")
    write(os.path.join(devices, "noactions", "__init__.py"), "async def get_state():\n    return {}\n")
    write(os.path.join(devices, "nostate", "__init__.py"), "async def a():\n    pass\nactions = [a]\n")
    sys.path.insert(0, tmp)
    try:
        for name in ("noactions", "nostate"):
            try:
                device_handler.load_device(devices, "contract_devices", name)
            except ValueError:
                continue
            raise AssertionError(f"expected ValueError for {name}")
    finally:
        sys.path.remove(tmp)


def test_sync_actions_work_too(tmp):
    devices = os.path.join(tmp, "sync_devices")
    write(os.path.join(devices, "__init__.py"), "")
    write(os.path.join(devices, "plain", "__init__.py"),
          "_state = {'n': 0}\n"
          "def bump(by=1, **params):\n    _state['n'] += by\n"
          "def get_state():\n    return dict(_state)\n"
          "actions = [bump]\n")
    sys.path.insert(0, tmp)
    try:
        device_handler.load_device(devices, "sync_devices", "plain")
        reply = run(device_handler.execute("bump", {"by": 3}))
        assert reply == {"ok": True, "state": {"n": 3}}, reply
    finally:
        sys.path.remove(tmp)


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
