"""End to end: a real server with a light and a thermostat client over real sockets.

This is the spec's Part 2 "Done when", plus the handshake, the dashboard API
and an unknown message type from its Tests section. Everything runs from temp
configs, so the real data folders are not touched.
"""
import json
import os
import socket
import sys
import time
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import System, wait_for, with_system  # noqa: E402,F401
from helpers import run_tests  # noqa: E402


def test_done_when(tmp):
    def scenario(system):
        system.start_server()
        system.start_client("e2e-light", "light")
        system.start_client("e2e-thermo", "thermostat")

        # both connected, each says what it is, the unprompted state arrived
        light = wait_for(lambda: (c := system.client("e2e-light")) and c["last_state"] and c, "the light")
        thermo = wait_for(lambda: (c := system.client("e2e-thermo")) and c["last_state"] and c, "the thermostat")
        assert light["device"] == "light" and light["capabilities"] == ["turn_on", "turn_off", "set_brightness"], light
        assert thermo["device"] == "thermostat" and thermo["capabilities"] == ["turn_on", "turn_off", "set_target"], thermo
        thermo_state = thermo["last_state"]
        thermo_port = thermo["port"]

        # the right client runs it and the server prints a successful result
        system.command("do e2e-light set_brightness level=40")
        wait_for(lambda: '"brightness": 40' in system.log("server"), "the successful result")
        wait_for(lambda: system.client("e2e-light")["last_state"]["brightness"] == 40, "the light's new state")
        assert system.client("e2e-thermo")["last_state"] == thermo_state, "the thermostat must not be touched"

        # the thermostat has no brightness, it fails cleanly and stays connected
        system.command("do e2e-thermo set_brightness level=40")
        wait_for(lambda: "unknown action 'set_brightness'" in system.log("server"), "the clean failure")
        time.sleep(0.5)
        still = system.client("e2e-thermo")
        assert still is not None and still["port"] == thermo_port, "the thermostat must keep its connection"

        # state is shorthand for do get_state, and list shows the device
        # the unprompted state printed the same JSON already, so look for the command's own line
        system.command("state e2e-thermo")
        wait_for(lambda: "get_state: {" in system.log("server"), "the state reply")
        system.command("list")
        wait_for(lambda: ") thermostat" in system.log("server") or ")\x1b[0m thermostat" in system.log("server"),
                 "list showing the device")

        # the dashboard page is the designed one
        with urllib.request.urlopen(f"http://127.0.0.1:{system.web_port}/", timeout=5) as r:
            assert "Pripojené zariadenia" in r.read().decode("utf-8")

        # the clients files follow the temp config, the real one is untouched
        assert os.path.exists(os.path.join(system.tmp, "clients.json"))

    with_system(tmp, scenario)


def test_handshake_and_unknown_type(tmp):
    def scenario(system):
        system.start_server()
        with socket.create_connection(("127.0.0.1", system.port), timeout=5) as sock:
            stream = sock.makefile("rwb")

            def send(message):
                stream.write(json.dumps(message).encode("utf-8") + b"\n")
                stream.flush()

            send({"type": "hello", "id": "e2e-raw", "name": "Raw", "role": "client",
                  "version": "test", "device": None, "capabilities": []})
            welcome = json.loads(stream.readline())
            assert welcome["type"] == "welcome" and welcome["role"] == "server", welcome
            assert "device_type" not in welcome, welcome

            send({"type": "bogus", "anything": 1})
            send({"type": "msg", "text": "still here"})
            wait_for(lambda: "still here" in system.log("server"), "the message after the unknown type")
            raw = system.client("e2e-raw")
            assert raw is not None and raw["device"] is None and raw["capabilities"] == [], raw

    with_system(tmp, scenario)


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
