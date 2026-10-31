"""End to end: v1.4 Part 3 "Done when", Find servers against a real server."""
import json
import os
import socket
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from e2e import wait_for, with_system  # noqa: E402
from launcher import discovery  # noqa: E402
from launcher.api import Api  # noqa: E402
from test_launcher_api import checkout  # noqa: E402
import make_certs  # noqa: E402

TOKEN = "s3cret-not-for-the-network"


def find(system):
    return discovery.find_servers(system.discovery_port, timeout=1, hosts=["127.0.0.1"])


def tls_server(system):
    make_certs.make_certs(os.path.join(system.tmp, "certs"), ["localhost", "127.0.0.1"])
    system.start_server(TOKEN=TOKEN, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")


def test_a_running_server_is_found_with_nothing_secret(tmp):
    def scenario(system):
        tls_server(system)
        assert f"Discovery answering on UDP port {system.discovery_port}" in system.log("server")
        servers = wait_for(lambda: find(system), "the answer")
        assert len(servers) == 1
        server = servers[0]
        assert (server["id"], server["name"], server["port"], server["web_port"], server["host"]) == (
            "e2e-server", "E2E server", system.port, system.web_port, "127.0.0.1")
        assert server["tls"] and server["token_required"]
        with open(os.path.join(system.tmp, "certs", "ca.crt"), encoding="ascii") as f:
            assert server["fingerprint"] == discovery.ca_fingerprint(f.read())
        assert TOKEN not in json.dumps(server)

        # the ca.crt the dashboard gives is the one the answer named
        pem = discovery.fetch_ca("127.0.0.1", server["web_port"], server["fingerprint"])
        assert discovery.ca_fingerprint(pem) == server["fingerprint"]
        try:
            discovery.fetch_ca("127.0.0.1", server["web_port"], "00:11")
            raise AssertionError("a ca.crt with another fingerprint must be refused")
        except discovery.CAError as e:
            assert "odtlačok" in str(e)

    with_system(tmp, scenario)


def test_a_client_made_from_a_found_server_connects_with_tls(tmp):
    def scenario(system):
        tls_server(system)
        root = checkout(tmp)
        api = Api(root, discovery_hosts=["127.0.0.1"])
        # the checkout's server config points Find servers at this server's port
        path = os.path.join(root, "server", "data", "config.json")
        data = json.load(open(path, encoding="utf-8"))
        data["DISCOVERY_PORT"] = system.discovery_port
        json.dump(data, open(path, "w", encoding="utf-8"))

        server = wait_for(lambda: api.find_servers(), "the answer")[0]
        assert server["here"] is False, "another checkout's server"
        answer = api.save_client({"name": "Chodba svetlo", "id": "chodba-svetlo", "device": "light",
                                  "host": server["host"], "port": str(server["port"]), "token": TOKEN,
                                  "tls": True, "server": server})
        assert answer["ok"], answer
        config = json.load(open(os.path.join(root, "client", "data", "chodba-svetlo.json"), encoding="utf-8"))
        assert config["TLS_CA"] == "certs/ca.crt" and config["TOKEN"] == TOKEN
        ca = os.path.join(root, "client", "data", "certs", "ca.crt")
        with open(ca, encoding="ascii") as f:
            assert discovery.ca_fingerprint(f.read()) == server["fingerprint"]

        system.start_client("chodba-svetlo", "light", TOKEN=TOKEN, TLS_CA=ca, HOST=config["HOST"])
        wait_for(lambda: system.client("chodba-svetlo"), "the client over TLS")
        assert "(TLS)" in system.log("chodba-svetlo")

    with_system(tmp, scenario)


def test_a_server_without_tls_cannot_be_saved_with_tls(tmp):
    def scenario(system):
        system.start_server()
        root = checkout(tmp)
        api = Api(root, discovery_hosts=["127.0.0.1"])
        server = wait_for(lambda: find(system), "the answer")[0]
        answer = api.save_client({"name": "X", "id": "x", "device": "", "host": "127.0.0.1",
                                  "port": str(server["port"]), "tls": True, "server": {**server, "here": False}})
        assert not answer["ok"] and "nemá TLS" in answer["errors"]["tls"]

    with_system(tmp, scenario)


def test_discovery_off_stays_silent(tmp):
    def scenario(system):
        system.start_server(DISCOVERY=False)
        assert "Discovery" not in system.log("server")
        assert find(system) == []

    with_system(tmp, scenario)


def test_a_taken_discovery_port_is_a_warning_not_a_stop(tmp):
    def scenario(system):
        taken = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        taken.bind(("127.0.0.1", system.discovery_port))
        try:
            system.start_server()
            assert f"Discovery off, UDP port {system.discovery_port} already in use" in system.log("server")
            assert system.api() is not None, "the server runs on"
        finally:
            taken.close()

    with_system(tmp, scenario)
