"""Real process harness for the end to end tests: a server and clients from temp configs.

Not a test file itself, the test_*_e2e.py files import it.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
SERVER_DIR = os.path.join(ROOT_DIR, "server")
CLIENT_DIR = os.path.join(ROOT_DIR, "client")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# the apps print ✔ and ✘, which a piped stdout on windows cannot encode otherwise
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
WAIT_SECONDS = 20


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(check, what):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


class System:
    """A server and clients started from temp configs. close() stops them all."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.port = free_port()
        self.web_port = free_port()
        self.processes = []
        self.logs = {}
        self.server = None

    def start(self, name, app_dir, config, stdin=subprocess.DEVNULL):
        config_path = os.path.join(self.tmp, f"{name}.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)
        log_path = os.path.join(self.tmp, f"{name}.log")
        log = open(log_path, "w", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "app.py", "--config", config_path],
            cwd=app_dir, stdin=stdin, stdout=log, stderr=subprocess.STDOUT,
            env=ENV, creationflags=NO_WINDOW,
        )
        log.close()
        self.processes.append(process)
        self.logs[name] = log_path
        return process

    def start_server(self, **extra):
        self.server = self.start("server", SERVER_DIR, {
            "ID": "e2e-server", "NAME": "E2E server", "TYPE": "server", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": self.port,
            "WEB_HOST": "127.0.0.1", "WEB_PORT": self.web_port,
            **extra,
        }, stdin=subprocess.PIPE)
        wait_for(lambda: self.api() is not None, "the dashboard to answer")

    def start_client(self, client_id, device=None, **extra):
        self.start(client_id, CLIENT_DIR, {
            "ID": client_id, "NAME": client_id.title(), "TYPE": "client", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": self.port, "DEVICE": device,
            **extra,
        })

    def api(self):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.web_port}/api/clients", timeout=2) as r:
                return json.load(r)["clients"]
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def client(self, client_id):
        for client in self.api() or []:
            if client["id"] == client_id:
                return client
        return None

    def command(self, line):
        self.server.stdin.write((line + "\n").encode("utf-8"))
        self.server.stdin.flush()

    def log(self, name):
        return read_text(self.logs[name])

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if self.server is not None and self.server.stdin:
            self.server.stdin.close()

    def dump_logs(self):
        for name, path in self.logs.items():
            print(f"----- {name}.log -----")
            print(read_text(path)[-3000:])


def with_system(tmp, scenario):
    system = System(tmp)
    try:
        scenario(system)
    except BaseException:
        system.close()
        system.dump_logs()
        raise
    system.close()
