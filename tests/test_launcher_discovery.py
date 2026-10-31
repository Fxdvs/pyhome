"""launcher/discovery.py: asking for servers, reading their answers, checking a fetched ca.crt."""
import json
import os
import socket
import sys
import threading

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from launcher import discovery  # noqa: E402

GOOD = {"type": "pyhome-server", "version": 1, "id": "dom", "name": "Dom", "port": 50000, "web_port": 50001,
        "tls": True, "fingerprint": "AB:CD", "token_required": True}


def encode(message):
    return json.dumps(message).encode()


def test_parse_a_good_answer():
    assert discovery.parse_answer(encode(GOOD)) == {key: GOOD[key] for key in
                                                   ("id", "name", "port", "web_port", "tls", "fingerprint", "token_required")}


def test_extra_fields_are_dropped():
    answer = discovery.parse_answer(encode({**GOOD, "TOKEN": "leaked", "x": 1}))
    assert "TOKEN" not in answer and "x" not in answer


@pytest.mark.parametrize("bad", [
    {**GOOD, "type": "pyhome-discover"},
    {**GOOD, "version": 2},
    {**GOOD, "id": ""},
    {**GOOD, "id": 5},
    {**GOOD, "port": 0},
    {**GOOD, "port": "50000"},
    {**GOOD, "port": True},
    {**GOOD, "web_port": 70000},
    {**GOOD, "tls": "yes"},
    {**GOOD, "token_required": None},
    {**GOOD, "fingerprint": None},
    {**GOOD, "tls": False},
])
def test_malformed_answers_are_ignored(bad):
    assert discovery.parse_answer(encode(bad)) is None


def test_junk_and_oversized_answers_are_ignored():
    assert discovery.parse_answer(b"not json") is None
    assert discovery.parse_answer(b"\xff\xfe") is None
    assert discovery.parse_answer(encode([GOOD])) is None
    assert discovery.parse_answer(encode({**GOOD, "pad": "x" * 3000})) is None


def test_targets_broadcast_and_this_computer():
    targets = discovery.targets()
    assert targets[0] == "255.255.255.255" and targets[-1] == "127.0.0.1"
    assert len(targets) == len(set(targets))
    for address in discovery.local_addresses():
        assert address.rsplit(".", 1)[0] + ".255" in targets


class FakeServers:
    """A UDP socket that answers every request with the given datagrams."""

    def __init__(self, *answers):
        self.answers = answers
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.requests = []
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except OSError:
                return
            self.requests.append(data)
            for answer in self.answers:
                self.sock.sendto(answer, addr)

    def close(self):
        self.sock.close()


def test_find_servers_keeps_the_good_answers_once():
    other = {**GOOD, "id": "chata", "name": "Chata", "tls": False, "fingerprint": None}
    fake = FakeServers(encode(GOOD), b"junk", encode(GOOD), encode(other), encode({**GOOD, "port": -1}))
    try:
        servers = discovery.find_servers(fake.port, timeout=0.5, hosts=["127.0.0.1"])
    finally:
        fake.close()
    assert [json.loads(r) for r in fake.requests] == [{"type": "pyhome-discover", "version": 1}]
    assert [(s["name"], s["host"], s["addresses"]) for s in servers] == [
        ("Chata", "127.0.0.1", ["127.0.0.1"]), ("Dom", "127.0.0.1", ["127.0.0.1"])]


def test_find_servers_with_nobody_there():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert discovery.find_servers(port, timeout=0.3, hosts=["127.0.0.1"]) == []


def test_ca_fingerprint_matches_the_server(tmp):
    import make_certs
    from handlers.tls import fingerprint
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    path = os.path.join(tmp, "certs", "ca.crt")
    with open(path, encoding="ascii") as f:
        assert discovery.ca_fingerprint(f.read()) == fingerprint(path)


def test_fetch_ca_from_nowhere_says_why():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(discovery.CAError, match="nedá stiahnuť"):
        discovery.fetch_ca("127.0.0.1", port, "AB:CD", timeout=2)
