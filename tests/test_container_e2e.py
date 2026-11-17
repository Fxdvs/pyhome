"""End to end: v1.5 Part 1 "Done when", the server as a container runs it, without a container."""
import os
import signal
import sys
import time

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM is how docker stops a server, on linux")


@posix_only
def test_sigterm_stops_the_server_cleanly(tmp):
    def scenario(system):
        system.start_server()
        system.start_client("e2e-light", "light")
        wait_for(lambda: system.client("e2e-light"), "the light")
        assert os.path.exists(os.path.join(system.tmp, "pyhome.db-wal"))

        started = time.monotonic()
        # stdin stays open, as under docker with a tty: nothing may wait for a line
        system.server.send_signal(signal.SIGTERM)
        assert system.server.wait(timeout=10) == 0
        assert time.monotonic() - started < 5
        log = system.log("server")
        assert "is shutting down (SIGTERM)" in log, log
        assert "Traceback" not in log and "Fatal" not in log, log
        assert "e2e-light" in log.split("is shutting down (SIGTERM)")[1], "the client was let go in order"
        assert not os.path.exists(os.path.join(system.tmp, "pyhome.db-wal")), "the store was closed"

    with_system(tmp, scenario)
