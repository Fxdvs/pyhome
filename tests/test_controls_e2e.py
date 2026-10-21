"""End to end: v1.1 Part 2 "Done when", device actions from the dashboard API with real processes."""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402

TOKEN = "s3cret-e2e"


def test_dashboard_controls_devices(tmp):
    def scenario(system):
        system.start_server(TOKEN=TOKEN)
        system.start_client("e2e-light", "light", TOKEN=TOKEN)
        system.start_client("e2e-thermo", "thermostat", TOKEN=TOKEN)
        wait_for(lambda: system.client("e2e-light") and system.client("e2e-thermo"), "both clients")

        def do(client_id, action, params=None, token=TOKEN):
            body = {"action": action} if params is None else {"action": action, "params": params}
            return system.post(f"/api/clients/{client_id}/do", body, token)

        # the light turns on and off and takes a brightness, the answer carries the new state
        status, body = do("e2e-light", "turn_on")
        assert status == 200 and body["ok"] is True and body["state"]["on"] is True, body
        status, body = do("e2e-light", "set_brightness", {"level": 40})
        assert status == 200 and body["state"] == {"on": True, "brightness": 40}, body
        status, body = do("e2e-light", "turn_off")
        assert status == 200 and body["state"]["on"] is False, body

        # the thermostat's target changes and the dashboard sees it on the next read
        status, body = do("e2e-thermo", "set_target", {"temperature": 22.5})
        assert status == 200 and body["state"]["target"] == 22.5, body
        assert system.client("e2e-thermo")["last_state"]["target"] == 22.5

        # an out of range value is the device's own error, a 200 because the device answered
        status, body = do("e2e-thermo", "set_target", {"temperature": 99})
        assert (status, body) == (200, {"ok": False, "error": "temperature must be a number from 5 to 30"}), body

        # refused before reaching anyone
        assert do("e2e-thermo", "set_brightness", {"level": 1})[0] == 400
        assert do("e2e-nobody", "turn_on")[0] == 404
        assert do("e2e-light", "turn_on", token="wrong") == (401, {"error": "token required"})

        # every browser action shows on the server console
        wait_for(lambda: "Dashboard 127.0.0.1 → E2E-Light#e2e-light set_brightness {\"level\": 40}" in system.log("server"),
                 "the console line")

    with_system(tmp, scenario)


def test_no_controls_without_a_server_token(tmp):
    def scenario(system):
        system.start_server()
        system.start_client("e2e-light", "light")
        wait_for(lambda: system.client("e2e-light"), "the light")
        status, body = system.post("/api/clients/e2e-light/do", {"action": "turn_on"})
        assert (status, body) == (403, {"error": "set TOKEN on the server to control devices from the browser"}), body
        assert system.client("e2e-light")["last_state"]["on"] is False, "nothing may have been switched"

    with_system(tmp, scenario)
