"""End to end: the token with a real server and real clients, v1.0 Part 3 and v1.1 Part 1."""
import os
import sys
import urllib.request

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
        assert system.known_ids() == ["e2e-good"], system.known_ids()
        for name in ("server", "e2e-good", "e2e-bad", "e2e-none"):
            log = system.log(name)
            assert TOKEN not in log and WRONG not in log, name

    with_system(tmp, scenario)


def test_token_protects_the_dashboard(tmp):
    def scenario(system):
        system.start_server(TOKEN=TOKEN)
        system.start_client("e2e-lamp", "light", TOKEN=TOKEN)
        wait_for(lambda: system.client("e2e-lamp"), "the client to show on the dashboard")

        # the page and the status are public, the page needs them to ask for the token
        assert system.http("/api/status") == (200, {"token_required": True, "controls": True})
        with urllib.request.urlopen(f"http://127.0.0.1:{system.web_port}/", timeout=5) as r:
            assert r.status == 200

        # the data is not
        assert system.http("/api/clients") == (401, {"error": "token required"})
        assert system.http("/api/clients", WRONG) == (401, {"error": "token required"})
        status, body = system.http("/api/clients", TOKEN)
        assert status == 200 and [c["id"] for c in body["clients"]] == ["e2e-lamp"], body

        server_log = system.log("server")
        assert "anyone who can reach the dashboard" not in server_log, server_log
        assert TOKEN not in server_log and WRONG not in server_log

    with_system(tmp, scenario)


def test_no_token_accepts_everyone_with_a_warning(tmp):
    def scenario(system):
        system.start_server()
        assert "No TOKEN set" in system.log("server"), system.log("server")
        system.start_client("e2e-open", TOKEN="anything")
        system.start_client("e2e-plain")
        wait_for(lambda: system.client("e2e-open") and system.client("e2e-plain"), "both clients")

        # the dashboard stays open as in 1.0, and says so at startup
        assert system.http("/api/status") == (200, {"token_required": False, "controls": False})
        assert system.http("/api/clients")[0] == 200
        assert "anyone who can reach the dashboard" in system.log("server"), system.log("server")

    with_system(tmp, scenario)


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
