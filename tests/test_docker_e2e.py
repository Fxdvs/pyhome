"""End to end: v1.5 Part 2 "Done when", the real image under docker compose.

Slow and needs Docker, so it runs only with PYHOME_DOCKER_TESTS=1, as the CI
job docker sets it. PYHOME_DOCKER_BUILD_ARGS adds arguments to the build
(a sandbox behind a proxy needs --network host).
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, ROOT_DIR)

from e2e import ENV, CLIENT_DIR, free_port, free_udp_port, read_text, wait_for  # noqa: E402
from launcher import discovery  # noqa: E402

pytestmark = pytest.mark.skipif(os.environ.get("PYHOME_DOCKER_TESTS") != "1",
                                reason="needs Docker; set PYHOME_DOCKER_TESTS=1")

PROJECT = "pyhome-test"
IMAGE = f"{PROJECT}-server"
CONTAINER = "pyhome-test"
# planted in the build's copy of the repository: none of it may reach the image
PLANTED = {
    "server/data/config.json": '{"TOKEN": "PLANTED-SECRET"}',
    "server/data/pyhome.db": "PLANTED-SECRET",
    "server/data/certs/ca.key": "PLANTED-SECRET",
    "client/data/kuchyna.json": '{"TOKEN": "PLANTED-SECRET"}',
}


def run(*command, check=True, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)
    if check and result.returncode != 0:
        raise AssertionError(f"{' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def build_context(tmp):
    """The repository as git has it, plus planted secrets, in a folder of its own."""
    context = os.path.join(tmp, "context")
    files = run("git", "ls-files", "--cached", "--others", "--exclude-standard", cwd=ROOT_DIR).stdout.split()
    for name in files + [".dockerignore", "Dockerfile"]:
        source = os.path.join(ROOT_DIR, name)
        if os.path.isfile(source):
            os.makedirs(os.path.dirname(os.path.join(context, name)), exist_ok=True)
            shutil.copyfile(source, os.path.join(context, name))
    for name, text in PLANTED.items():
        os.makedirs(os.path.dirname(os.path.join(context, name)), exist_ok=True)
        with open(os.path.join(context, name), "w", encoding="utf-8") as f:
            f.write(text)
    return context


class Compose:
    def __init__(self, tmp, context):
        self.data = os.path.join(tmp, "server-data")
        os.makedirs(self.data)
        # the container writes as uid 1000; a runner's own user may be another
        os.chmod(self.data, 0o777)
        self.port, self.web_port, self.udp_port = free_port(), free_port(), free_udp_port()
        self.override = os.path.join(tmp, "compose.test.yml")
        with open(self.override, "w", encoding="utf-8") as f:
            f.write(f"""services:
  server:
    container_name: {CONTAINER}
    ports: !override
      - "127.0.0.1:{self.port}:50000"
      - "127.0.0.1:{self.web_port}:50001"
      - "127.0.0.1:{self.udp_port}:50002/udp"
    volumes: !override
      - "{self.data}:/data"
""")
        self.base = ["docker", "compose", "-p", PROJECT, "-f", os.path.join(context, "docker-compose.yml"),
                     "-f", self.override]

    def __call__(self, *args, check=True):
        return run(*self.base, *args, check=check)

    def health(self):
        return run("docker", "inspect", "-f", "{{.State.Health.Status}}", CONTAINER, check=False).stdout.strip()

    def logs(self):
        result = run("docker", "logs", CONTAINER, check=False)
        return result.stdout + result.stderr

    def api(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"http://127.0.0.1:{self.web_port}/api/clients", timeout=3) as response:
                return json.load(response)["clients"]
        except OSError:
            return None


@pytest.fixture
def compose(tmp):
    context = build_context(tmp)
    extra = shlex.split(os.environ.get("PYHOME_DOCKER_BUILD_ARGS", ""))
    run("docker", "build", *extra, "-t", IMAGE, context)
    compose = Compose(tmp, context)
    yield compose
    compose("down", check=False)


def test_the_server_in_docker(tmp, compose):
    # nothing planted reached the image, and the data folder in it holds only the example
    listing = run("docker", "run", "--rm", "--entrypoint", "sh", IMAGE, "-c",
                  "ls /app/server/data; grep -rl PLANTED-SECRET /app || true").stdout.split()
    assert listing == ["config.example.json"], listing
    assert run("docker", "run", "--rm", "--entrypoint", "id", IMAGE).stdout.startswith("uid=1000(pyhome)")

    compose("up", "-d", "--no-build")
    wait_for(lambda: compose.health() == "healthy", "a healthy container")
    assert os.path.exists(os.path.join(compose.data, "config.json")), "made from the example in the data folder"
    assert compose.api() == []

    servers = discovery.find_servers(compose.udp_port, hosts=["127.0.0.1"])
    assert [s["port"] for s in servers] == [50000], servers

    # a client from the checkout connects to the server in the container
    config = os.path.join(tmp, "light.json")
    with open(config, "w", encoding="utf-8") as f:
        json.dump({"ID": "docker-light", "NAME": "Docker light", "TYPE": "client", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": compose.port, "DEVICE": "light"}, f)
    log_path = os.path.join(tmp, "light.log")
    with open(log_path, "w", encoding="utf-8") as log:
        light = subprocess.Popen([sys.executable, "app.py", "--config", config], cwd=CLIENT_DIR, env=ENV,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_for(lambda: [c["id"] for c in compose.api() or [] if c["online"]] == ["docker-light"], "the light")

        started = time.monotonic()
        compose("stop")
        assert time.monotonic() - started < 10, "stopped by SIGTERM, not killed after the grace period"
        assert run("docker", "inspect", "-f", "{{.State.ExitCode}}", CONTAINER).stdout.strip() == "0"
        logs = compose.logs()
        assert "is shutting down (SIGTERM)" in logs and "Traceback" not in logs, logs
        assert not os.path.exists(os.path.join(compose.data, "pyhome.db-wal")), "the store was closed"

        compose("up", "-d", "--no-build")
        wait_for(lambda: compose.health() == "healthy", "healthy again")
        assert "1 clients known" in compose.logs()
        wait_for(lambda: "docker-light" in [c["id"] for c in compose.api() or [] if c["online"]], "the light again")
    finally:
        light.kill()
        light.wait(timeout=10)
    assert "Connected to" in read_text(log_path)
