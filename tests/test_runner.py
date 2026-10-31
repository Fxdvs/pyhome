"""launcher/runner.py with a small Python child instead of a real app."""
import os
import sys
import textwrap
import time

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from launcher.runner import Runner  # noqa: E402

# answers like an app: echoes input, colors, ends on shutdown + y
CHILD = """
import sys
print("\\033[92mready\\033[0m", flush=True)
print("Spálňa ✔", flush=True)
for line in sys.stdin:
    line = line.strip()
    if line == "shutdown":
        print("Are you sure? (y/n)", flush=True)
        if sys.stdin.readline().strip() == "y":
            print("is shutting down", flush=True)
            sys.exit(0)
    elif line == "fail":
        print("boom", flush=True)
        sys.exit(3)
    else:
        print("got " + line, flush=True)
"""

# ignores shutdown, so only terminate ends it
DEAF = """
import sys, time
print("ready", flush=True)
for line in sys.stdin:
    pass
time.sleep(60)
"""


def child(tmp, source, name="child.py", **kwargs):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(source))
    return Runner([sys.executable, path], cwd=tmp, **kwargs)


def texts(runner, since=0):
    return [text for _, text in runner.output(since)["lines"]]


def wait_for(check, what, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def test_output_kept_with_colors_and_utf8(tmp):
    runner = child(tmp, CHILD)
    assert runner.start()
    try:
        wait_for(lambda: "Spálňa ✔" in texts(runner), "the output")
        assert texts(runner)[:2] == ["\033[92mready\033[0m", "Spálňa ✔"]
        assert runner.status()["state"] == "running" and runner.status()["uptime"] >= 0
    finally:
        runner.stop()


def test_input_goes_to_the_app_and_is_shown(tmp):
    runner = child(tmp, CHILD)
    runner.start()
    try:
        wait_for(lambda: "Spálňa ✔" in texts(runner), "the output")
        assert runner.send("do kuch turn_on")
        wait_for(lambda: "got do kuch turn_on" in texts(runner), "the answer")
        assert "\033[94m> do kuch turn_on\033[0m" in texts(runner)
    finally:
        runner.stop()


def test_output_since_a_line_number(tmp):
    runner = child(tmp, CHILD)
    runner.start()
    try:
        wait_for(lambda: len(texts(runner)) >= 2, "the output")
        first = runner.output(0)
        assert [number for number, _ in first["lines"]] == [1, 2] and first["last"] == 2
        assert runner.output(first["last"]) == {"lines": [], "last": 2}
        runner.send("a")
        wait_for(lambda: "got a" in texts(runner, 2), "the new line")
        assert [text for _, text in runner.output(2)["lines"]][-1] == "got a"
    finally:
        runner.stop()


def test_buffer_keeps_the_newest_lines(tmp):
    runner = child(tmp, "for i in range(25):\n    print(i, flush=True)\n", limit=10)
    runner.start()
    wait_for(lambda: runner.status()["state"] != "running", "the end")
    wait_for(lambda: "Zastavené" in texts(runner)[-1], "the note")
    lines = runner.output(0)["lines"]
    assert len(lines) == 10
    # numbers keep counting, so the page knows lines were dropped
    assert lines[0][0] == 17 and lines[-2] == [25, "24"]


def test_stop_types_shutdown_and_y(tmp):
    runner = child(tmp, CHILD)
    runner.start()
    wait_for(lambda: "Spálňa ✔" in texts(runner), "the output")
    started = time.monotonic()
    runner.stop()
    assert time.monotonic() - started < 3, "ended by shutdown, not by the terminate after the grace time"
    assert "is shutting down" in texts(runner)
    assert runner.status() == {"state": "stopped", "code": 0, "uptime": None}
    assert texts(runner)[-1] == "\033[90mZastavené.\033[0m"


def test_stop_terminates_an_app_that_does_not_listen(tmp):
    runner = child(tmp, DEAF)
    runner.start()
    wait_for(lambda: "ready" in texts(runner), "the output")
    runner.stop(grace=0.5)
    assert not runner.is_running()
    # asked to stop, so not shown as an error even though the code is not 0
    assert runner.status()["state"] == "stopped"


@pytest.mark.skipif(sys.platform == "win32", reason="terminate is already a kill on windows")
def test_stop_kills_after_the_timeout(tmp):
    runner = child(tmp, """
        import signal, sys, time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        print("ready", flush=True)
        for line in sys.stdin:
            pass
        time.sleep(60)
    """)
    runner.start()
    wait_for(lambda: "ready" in texts(runner), "the output")
    started = time.monotonic()
    runner.stop(grace=0.3, kill_after=0.3)
    assert not runner.is_running() and time.monotonic() - started < 5


def test_an_app_that_fails_is_exited_with_its_code(tmp):
    runner = child(tmp, CHILD)
    runner.start()
    wait_for(lambda: "Spálňa ✔" in texts(runner), "the output")
    runner.send("fail")
    wait_for(lambda: runner.status()["state"] == "exited", "the exit")
    assert runner.status()["code"] == 3
    wait_for(lambda: texts(runner)[-1] == "\033[91mSkončilo s kódom 3.\033[0m", "the note")
    assert not runner.send("anything"), "nothing to type into"


def test_restart_keeps_the_old_output(tmp):
    runner = child(tmp, CHILD)
    runner.start()
    wait_for(lambda: "Spálňa ✔" in texts(runner), "the output")
    runner.stop()
    assert runner.start()
    try:
        wait_for(lambda: texts(runner).count("Spálňa ✔") == 2, "the second run")
        assert any("znova spustené" in text for text in texts(runner))
    finally:
        runner.stop()


def test_start_twice_is_refused(tmp):
    runner = child(tmp, CHILD)
    assert runner.start()
    try:
        assert not runner.start()
    finally:
        runner.stop()


def test_a_missing_program_is_reported(tmp):
    runner = Runner([os.path.join(tmp, "no-such-program")], cwd=tmp)
    assert not runner.start()
    assert "Nedá sa spustiť" in texts(runner)[-1]
    assert runner.status()["state"] == "stopped"
