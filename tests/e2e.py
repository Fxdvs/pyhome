"""Real process harness for the end to end tests: a server and clients from temp configs.

Not a test file itself, the test_*_e2e.py files import it.
"""
import contextlib
import json
import os
import socket
import sqlite3
import ssl
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


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
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
        # never 50002: a real server on this machine may answer there
        self.discovery_port = free_udp_port()
        self.processes = []
        self.logs = {}
        self.server = None
        # the server's TOKEN, sent to the dashboard API once the server has one
        self.token = None
        # with TLS the dashboard is https, verified against the server's own ca.crt
        self.scheme = "http"
        self.context = None

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
        self.token = extra.get("TOKEN") or None
        if extra.get("TLS_CERT"):
            # make_certs.py puts ca.crt next to server.crt
            ca = os.path.join(os.path.dirname(os.path.join(self.tmp, extra["TLS_CERT"])), "ca.crt")
            self.scheme = "https"
            # full verification, host name included, the way a browser does it
            self.context = ssl.create_default_context(cafile=ca)
        self.server = self.start("server", SERVER_DIR, {
            "ID": "e2e-server", "NAME": "E2E server", "TYPE": "server", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": self.port,
            "WEB_HOST": "127.0.0.1", "WEB_PORT": self.web_port,
            "DISCOVERY_PORT": self.discovery_port,
            **extra,
        }, stdin=subprocess.PIPE)
        wait_for(lambda: self.api() is not None, "the dashboard to answer")

    def start_client(self, client_id, device=None, stdin=subprocess.DEVNULL, **extra):
        return self.start(client_id, CLIENT_DIR, {
            "ID": client_id, "NAME": client_id.title(), "TYPE": "client", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": self.port, "DEVICE": device,
            **extra,
        }, stdin=stdin)

    def url(self, path):
        return f"{self.scheme}://127.0.0.1:{self.web_port}{path}"

    def http(self, path, token=None):
        """(status, parsed JSON body) of a GET to the dashboard. Raises when it does not answer."""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        request = urllib.request.Request(self.url(path), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=2, context=self.context) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            # an error status still carries a body, read it like a success
            with e:
                return e.code, json.load(e)

    def post(self, path, body, token=None):
        """(status, parsed JSON body) of a POST with a JSON body to the dashboard."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.url(path), data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10, context=self.context) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.load(e)

    def api(self):
        try:
            status, body = self.http("/api/clients", self.token)
        except (urllib.error.URLError, OSError, ValueError):
            return None
        return body["clients"] if status == 200 else None

    def client(self, client_id):
        """The client as the dashboard API shows it, only while it is online."""
        found = self.known(client_id)
        return found if found and found["online"] else None

    def known(self, client_id):
        """The client as the dashboard API shows it, online or offline."""
        for client in self.api() or []:
            if client["id"] == client_id:
                return client
        return None

    def known_ids(self):
        """The ids in the server's pyhome.db, read the way any SQLite browser would, without writing."""
        uri = "file:" + os.path.join(self.tmp, "pyhome.db").replace("\\", "/") + "?mode=ro"
        with contextlib.closing(sqlite3.connect(uri, uri=True)) as db:
            return sorted(row[0] for row in db.execute("SELECT id FROM clients"))

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
