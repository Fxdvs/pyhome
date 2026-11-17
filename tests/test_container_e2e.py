"""End to end: v1.5 Part 1 "Done when", the server as a container runs it, without a container."""
import json
import os
import signal
import subprocess
import sys
import time

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)

from e2e import ENV, NO_WINDOW, SERVER_DIR, free_port, free_udp_port, read_text, wait_for, with_system  # noqa: E402

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


def test_pyhome_data_and_pyhome_address(tmp):
    data = os.path.join(tmp, "data")
    env = dict(ENV, PYHOME_DATA=data, PYHOME_ADDRESS="192.168.1.20")
    # no --config: the data folder is empty, as a fresh container's mount
    log_path = os.path.join(tmp, "server.log")
    with open(log_path, "w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "app.py"], cwd=SERVER_DIR, env=env, creationflags=NO_WINDOW,
                                  stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_for(lambda: os.path.exists(os.path.join(data, "config.json")), "the config")
        # move it off the real ports before it gets far, then start again on free ones
        server.kill()
        server.wait(timeout=10)
        with open(os.path.join(data, "config.json"), encoding="utf-8") as f:
            config = json.load(f)
        assert config["TOKEN"] == "" and config["NAME"] == "Server"
        web_port = free_port()
        config.update(HOST="127.0.0.1", PORT=free_port(), WEB_PORT=web_port, DISCOVERY_PORT=free_udp_port())
        with open(os.path.join(data, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f)
        with open(log_path, "w", encoding="utf-8") as log:
            server = subprocess.Popen([sys.executable, "app.py"], cwd=SERVER_DIR, env=env, creationflags=NO_WINDOW,
                                      stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        wait_for(lambda: "Dashboard running on" in read_text(log_path), "the dashboard line")
        wait_for(lambda: f"http://192.168.1.20:{web_port}" in read_text(log_path), "the address the house uses")
        assert os.path.exists(os.path.join(data, "pyhome.db")), "the database lives in the data folder"
    finally:
        server.kill()
        server.wait(timeout=10)
        if server.stdin:
            server.stdin.close()


def test_make_certs_follows_pyhome_data_and_address(tmp):
    pytest.importorskip("cryptography")
    from cryptography import x509
    data = os.path.join(tmp, "data")
    env = dict(ENV, PYHOME_DATA=data, PYHOME_ADDRESS="dom.lan")
    result = subprocess.run([sys.executable, "make_certs.py"], cwd=SERVER_DIR, env=env,
                            capture_output=True, text=True, encoding="utf-8", creationflags=NO_WINDOW)
    assert result.returncode == 0, result.stdout + result.stderr
    with open(os.path.join(data, "certs", "server.crt"), "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    assert "dom.lan" in names


@posix_only
def test_ctrl_c_ends_the_server_with_its_console_open(tmp):
    def scenario(system):
        system.start_server()
        # Ctrl+C at an attached terminal: SIGINT while the console waits for a line
        system.server.send_signal(signal.SIGINT)
        assert system.server.wait(timeout=10) == 0
        assert "is turned off" in system.log("server")
        assert not os.path.exists(os.path.join(system.tmp, "pyhome.db-wal")), "the store was closed"

    with_system(tmp, scenario)
