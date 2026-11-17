"""v1.5 Part 2 without Docker: what goes into the image, the compose file, the health check."""
import os
import re
import shutil
import subprocess
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))

from e2e import ENV, NO_WINDOW, SERVER_DIR, with_system  # noqa: E402


def read(name):
    with open(os.path.join(ROOT_DIR, name), encoding="utf-8") as f:
        return f.read()


def dockerignore_patterns():
    patterns = []
    for line in read(".dockerignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append((line.startswith("!"), line.lstrip("!").rstrip("/")))
    return patterns


def pattern_regex(pattern):
    """A .dockerignore pattern as a regex: ** any folders, * and ? within one name."""
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def in_context(path, patterns):
    """Whether Docker sends path to the build, by its rules: the last pattern that matches the path
    or one of its parent folders wins."""
    parts = path.split("/")
    candidates = ["/".join(parts[:n]) for n in range(1, len(parts) + 1)]
    sent = True
    for negated, pattern in patterns:
        regex = pattern_regex(pattern)
        if any(regex.match(c) for c in candidates):
            sent = negated
    return sent


SECRETS = [
    "server/data/config.json",
    "server/data/pyhome.db",
    "server/data/pyhome.db-wal",
    "server/data/pyhome-backup-20261117-1200.db",
    "server/data/certs/ca.key",
    "server/data/certs/server.key",
    "server/data/clients.json.imported",
    "server-data/config.json",
    "client/data/config.json",
    "client/data/certs/ca.crt",
    "launcher/state.json",
    "server/start.bat",
    "server/handlers/__pycache__/store.cpython-313.pyc",
    ".git/config",
    "tests/e2e.py",
]

NEEDED = [
    "requirements.txt",
    "server/app.py",
    "server/healthcheck.py",
    "server/make_certs.py",
    "server/handlers/store.py",
    "server/handlers/commands/shutdown.py",
    "server/web/index.html",
    "server/data/config.example.json",
    "shared/config.py",
    "shared/commands/help.py",
]


@pytest.mark.parametrize("path", SECRETS)
def test_secrets_never_reach_the_image(path):
    assert not in_context(path, dockerignore_patterns()), path


@pytest.mark.parametrize("path", NEEDED)
def test_the_server_reaches_the_image(path):
    assert in_context(path, dockerignore_patterns()), path


def test_every_file_the_server_has_is_sent():
    patterns = dockerignore_patterns()
    for folder in ("server", "shared"):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT_DIR, folder)):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "data", "certs")]
            for name in filenames:
                path = os.path.relpath(os.path.join(dirpath, name), ROOT_DIR).replace(os.sep, "/")
                if name.endswith((".pyc", ".bat")):
                    continue
                assert in_context(path, patterns), path


def test_dockerfile():
    dockerfile = read("Dockerfile")
    assert dockerfile.startswith("# ") and "FROM python:3.13-slim" in dockerfile
    assert "USER pyhome" in dockerfile and "--uid 1000" in dockerfile, "never root"
    assert "PYHOME_DATA=/data" in dockerfile and "VOLUME /data" in dockerfile
    assert "EXPOSE 50000 50001 50002/udp" in dockerfile
    assert 'CMD ["python", "healthcheck.py"]' in dockerfile and 'CMD ["python", "app.py"]' in dockerfile
    assert "COPY . " not in dockerfile, "only the server goes in"


def test_compose_files():
    compose = read("docker-compose.yml")
    for line in ('"50000:50000"', '"50001:50001"', '"50002:50002/udp"', "./server-data:/data",
                 "restart: unless-stopped", "stdin_open: true", "tty: true", "stop_grace_period: 15s",
                 "hostname: pyhome", "TZ: ${TZ:-Europe/Bratislava}", "PYHOME_ADDRESS: ${PYHOME_ADDRESS:-}"):
        assert line in compose, line
    host = read("docker-compose.host.yml")
    assert "network_mode: host" in host and "ports: !reset []" in host and "hostname: !reset null" in host
    assert "server-data/" in read(".gitignore").splitlines() and ".env" in read(".gitignore").splitlines()


def healthcheck(data_dir):
    return subprocess.run([sys.executable, "healthcheck.py"], cwd=SERVER_DIR, env=dict(ENV, PYHOME_DATA=data_dir),
                          capture_output=True, text=True, creationflags=NO_WINDOW, timeout=30)


@pytest.mark.parametrize("tls", [False, True])
def test_healthcheck_against_a_real_server(tmp, tls):
    def scenario(system):
        extra = {}
        if tls:
            import make_certs
            make_certs.make_certs(os.path.join(system.tmp, "certs"), ["localhost", "127.0.0.1"])
            extra = {"TLS_CERT": "certs/server.crt", "TLS_KEY": "certs/server.key"}
        system.start_server(**extra)
        # the check reads the config from PYHOME_DATA, as in the container
        shutil.copyfile(os.path.join(system.tmp, "server.json"), os.path.join(system.tmp, "config.json"))
        result = healthcheck(system.tmp)
        assert result.returncode == 0, result.stdout + result.stderr

        system.server.kill()
        system.server.wait(timeout=10)
        result = healthcheck(system.tmp)
        assert result.returncode == 1 and "127.0.0.1" in result.stdout

    with_system(tmp, scenario)
