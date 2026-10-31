"""One app run inside the launcher: started with pipes, its output kept, its input written.

The app is the same `python app.py --config <file>` a console runs, but
without a console window: stdout and stderr go into a buffer the page
reads, and a line typed in the page goes to its stdin. The apps see no
terminal, so they print plain lines and draw no prompt (shared.console).
"""
import collections
import os
import subprocess
import threading
import time

# no console window for the app, on windows; elsewhere there is none anyway
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# lines kept per app; older ones are dropped
LIMIT = 5000

# Stop: shutdown and y, then terminate after STOP_GRACE seconds, then kill after KILL_AFTER more
STOP_GRACE = 3
KILL_AFTER = 5

# the launcher's own lines in an app's output, colored like the apps color theirs
GRAY = "\033[90m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


class Runner:
    """An app the launcher can start, talk to and stop. Thread safe: the page calls it from many threads."""

    def __init__(self, command, cwd, limit=LIMIT):
        self.command = command
        self.cwd = cwd
        self.process = None
        self.started_at = None
        self._lines = collections.deque(maxlen=limit)
        self._next = 1
        self._lock = threading.Lock()
        self._reader = None
        # set by stop(), so an exit the launcher asked for is not shown as an error
        self._stopping = False

    # output

    def _add(self, text):
        with self._lock:
            self._lines.append((self._next, text))
            self._next += 1

    def note(self, text, color=GRAY):
        """A line from the launcher itself in the app's output."""
        self._add(f"{color}{text}{RESET}")

    def output(self, since=0):
        """{"lines": [[number, text], ...] after line number since, "last": the newest number}."""
        with self._lock:
            lines = [[number, text] for number, text in self._lines if number > since]
            return {"lines": lines, "last": self._next - 1}

    # lifecycle

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def status(self):
        """{"state": running, stopped or exited, "code", "uptime" in seconds while running}.

        exited means it ended on its own with an error; ended by Stop, or by
        its own shutdown (code 0), it is stopped.
        """
        if self.process is None:
            return {"state": "stopped", "code": None, "uptime": None}
        code = self.process.poll()
        if code is None:
            return {"state": "running", "code": None, "uptime": round(time.time() - self.started_at)}
        state = "stopped" if code == 0 or self._stopping else "exited"
        return {"state": state, "code": code, "uptime": None}

    def start(self):
        """Start the app. False when it already runs or cannot be started (the reason is in its output)."""
        if self.is_running():
            return False
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        if self._next > 1:
            self.note("─" * 12 + " znova spustené " + "─" * 12)
        try:
            self.process = subprocess.Popen(
                self.command, cwd=self.cwd, env=env, creationflags=NO_WINDOW,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        except OSError as e:
            self.process = None
            self.note(f"Nedá sa spustiť: {e}", RED)
            return False
        self._stopping = False
        self.started_at = time.time()
        self._reader = threading.Thread(target=self._read, args=(self.process,), daemon=True)
        self._reader.start()
        return True

    def _read(self, process):
        # bytes, decoded here: a stray byte must not end the reading
        for raw in iter(process.stdout.readline, b""):
            self._add(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
        code = process.wait()
        process.stdout.close()
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        if self._stopping or code == 0:
            self.note("Zastavené.")
        else:
            self.note(f"Skončilo s kódom {code}.", RED)

    def _write(self, line):
        try:
            self.process.stdin.write((line + "\n").encode("utf-8"))
            self.process.stdin.flush()
            return True
        except (OSError, ValueError, AttributeError):
            # the app ended in the meantime, its stdin is gone
            return False

    def send(self, line):
        """Type a line into the app, as in its own console. Shown in the output. False when it is not running."""
        if not self.is_running():
            return False
        self._add(f"{BLUE}> {line}{RESET}")
        return self._write(line)

    def stop(self, grace=STOP_GRACE, kill_after=KILL_AFTER):
        """End the app the way a person would: shutdown, y. Then terminate, then kill. Blocks until it ended."""
        process = self.process
        if process is None or process.poll() is not None:
            return
        self._stopping = True
        self.note("Zastavujem...")
        self._write("shutdown")
        self._write("y")
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=kill_after)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if self._reader is not None:
            self._reader.join(timeout=2)
