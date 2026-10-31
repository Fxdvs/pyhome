"""End to end: the apps stopped the way the launcher stops them, by typing shutdown and y."""
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from e2e import wait_for, with_system  # noqa: E402


def type_lines(process, *lines):
    process.stdin.write("".join(line + "\n" for line in lines).encode("utf-8"))
    process.stdin.flush()


def assert_clean(log):
    assert "is shutting down" in log, log
    # an orderly exit: no traceback, no task destroyed while pending, no prompt drawn into a pipe
    assert "Traceback" not in log and "destroyed" not in log, log
    assert "\r" not in log and "> " not in log, log


def test_shutdown_ends_the_server_cleanly_and_closes_the_database(tmp):
    def scenario(system):
        system.start_server()
        light = system.start_client("e2e-light", "light", stdin=subprocess.PIPE)
        wait_for(lambda: system.client("e2e-light"), "the light")
        assert os.path.exists(os.path.join(system.tmp, "pyhome.db-wal")), "a running server has a WAL file"

        type_lines(system.server, "shutdown", "y")
        assert system.server.wait(timeout=15) == 0
        assert_clean(system.log("server"))
        assert not os.path.exists(os.path.join(system.tmp, "pyhome.db-wal")), "closing folds the WAL back"

        type_lines(light, "shutdown", "y")
        assert light.wait(timeout=15) == 0
        assert_clean(system.log("e2e-light"))

    with_system(tmp, scenario)


def test_shutdown_can_be_cancelled(tmp):
    def scenario(system):
        system.start_server()
        type_lines(system.server, "shutdown", "n")
        wait_for(lambda: "Operation cancelled" in system.log("server"), "the cancel")
        assert system.server.poll() is None
        assert system.api() is not None, "the dashboard still answers"

    with_system(tmp, scenario)
