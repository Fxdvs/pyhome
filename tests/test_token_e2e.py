"""End to end: the spec's Part 3 "Done when" with a real server and real clients."""
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402
from helpers import run_tests  # noqa: E402

TOKEN = "s3cret-e2e"
WRONG = "wrong-guess-123"


def test_token_protects_the_server(tmp):
    def scenario(system):
        system.start_server(TOKEN=TOKEN)
        system.start_client("e2e-good", TOKEN=TOKEN)
        system.start_client("e2e-bad", TOKEN=WRONG)
        system.start_client("e2e-none")

        # the right token connects, the others are refused with a readable reason
        wait_for(lambda: system.client("e2e-good"), "the client with the right token")
        wait_for(lambda: "wrong token" in system.log("e2e-bad"), "the refusal of the wrong token")
        wait_for(lambda: "needs a token" in system.log("e2e-none"), "the refusal of a missing token")
        assert "reconnect" in system.log("e2e-bad"), "the client should say how to fix it"
        assert system.client("e2e-bad") is None and system.client("e2e-none") is None

        server_log = system.log("server")
        assert server_log.count("Refused") == 2, server_log
        assert "No TOKEN set" not in server_log

        # refused clients are not saved, and the token is never printed anywhere
        with open(os.path.join(system.tmp, "clients.json"), encoding="utf-8") as f:
            assert [c["ID"] for c in json.load(f)] == ["e2e-good"]
        for name in ("server", "e2e-good", "e2e-bad", "e2e-none"):
            log = system.log(name)
            assert TOKEN not in log and WRONG not in log, name

    with_system(tmp, scenario)


def test_no_token_accepts_everyone_with_a_warning(tmp):
    def scenario(system):
        system.start_server()
        assert "No TOKEN set" in system.log("server"), system.log("server")
        system.start_client("e2e-open", TOKEN="anything")
        system.start_client("e2e-plain")
        wait_for(lambda: system.client("e2e-open") and system.client("e2e-plain"), "both clients")

    with_system(tmp, scenario)


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
