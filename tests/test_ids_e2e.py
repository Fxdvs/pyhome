"""End to end: v1.1 Part 3 "Done when", readable ids and id prefixes with real processes."""
import json
import os
import re
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402
from helpers import run_tests  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_readable_ids_and_prefixes(tmp):
    def scenario(system):
        def server_log():
            return ANSI.sub("", system.log("server"))

        system.start_server()
        # an empty ID takes the config file's name
        system.start_client("kuchyna-svetlo", "light", ID="")
        system.start_client("obyvacka-termostat", "thermostat")
        wait_for(lambda: system.client("kuchyna-svetlo") and system.client("obyvacka-termostat"), "both clients")
        with open(os.path.join(system.tmp, "kuchyna-svetlo.json"), encoding="utf-8") as f:
            assert json.load(f)["ID"] == "kuchyna-svetlo"

        # the full id, a prefix and a prefix in capitals all reach the light
        system.command("do kuchyna-svetlo turn_on")
        wait_for(lambda: system.client("kuchyna-svetlo")["last_state"]["on"] is True, "the light on")
        system.command("do kuch turn_off")
        wait_for(lambda: system.client("kuchyna-svetlo")["last_state"]["on"] is False, "the light off")
        system.command("do KUCH turn_on")
        wait_for(lambda: system.client("kuchyna-svetlo")["last_state"]["on"] is True, "the light on again")
        assert "kuchyna-svetlo turn_off: {" in server_log(), "the full id is printed for a prefix"
        assert system.client("obyvacka-termostat")["last_state"]["on"] is False, "the thermostat is untouched"

        # a second kuchyna- makes kuch ambiguous, nothing is sent
        system.start_client("kuchyna-termostat", "thermostat")
        wait_for(lambda: system.client("kuchyna-termostat"), "the second kitchen client")
        system.command("do kuch turn_off")
        wait_for(lambda: "'kuch' matches 2 online clients: kuchyna-svetlo, kuchyna-termostat" in server_log(),
                 "the ambiguous prefix refused")
        assert system.client("kuchyna-svetlo")["last_state"]["on"] is True

        # send all still reaches everyone
        system.command("send all ahoj-vsetci")
        for client_id in ("kuchyna-svetlo", "obyvacka-termostat", "kuchyna-termostat"):
            wait_for(lambda: "ahoj-vsetci" in system.log(client_id), f"the message at {client_id}")

        # an id off the rule still connects, with a warning
        system.start_client("e2e-odd", ID="Kuchyňa 1")
        wait_for(lambda: system.client("Kuchyňa 1"), "the client with the odd id")
        assert "it cannot be typed in commands" in system.log("e2e-odd"), system.log("e2e-odd")
        assert "does not follow the id rule" not in system.log("kuchyna-svetlo")

    with_system(tmp, scenario)


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
