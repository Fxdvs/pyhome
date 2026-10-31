"""server/handlers/discovery.py: what the server answers on UDP, and what it does not answer."""
import asyncio
import json
import os
import socket
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from handlers import discovery  # noqa: E402
import make_certs  # noqa: E402

REQUEST = json.dumps({"type": "pyhome-discover", "version": 1}).encode()


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "dom", "NAME": "Domček", "TYPE": "server", "VERSION": "test", "HOST": "127.0.0.1",
                   "PORT": 50100, "WEB_PORT": 50101, "TOKEN": "s3cret", **values}, f)
    config.init(tmp, path)


def ask(datagrams, wait=0.3):
    """Start discovery on a free port, send datagrams from one socket, return what came back."""
    async def run():
        transport = await discovery.start_discovery(0)
        port = transport.get_extra_info("sockname")[1]
        asker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        asker.setblocking(False)
        try:
            for data in datagrams:
                asker.sendto(data, ("127.0.0.1", port))
            await asyncio.sleep(wait)
            answers = []
            while True:
                try:
                    answers.append(asker.recv(65535))
                except BlockingIOError:
                    return answers
        finally:
            asker.close()
            transport.close()
    return asyncio.run(run())


def test_answers_who_the_server_is(tmp):
    use_server_config(tmp)
    answers = ask([REQUEST])
    assert len(answers) == 1
    answer = json.loads(answers[0])
    assert answer == {"type": "pyhome-server", "version": 1, "id": "dom", "name": "Domček", "port": 50100,
                      "web_port": 50101, "tls": False, "fingerprint": None, "token_required": True}


def test_never_the_token(tmp):
    use_server_config(tmp)
    assert b"s3cret" not in ask([REQUEST])[0]


def test_tls_gives_the_fingerprint_of_ca_crt(tmp):
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    use_server_config(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key", TOKEN="")
    answer = json.loads(ask([REQUEST])[0])
    from handlers.tls import fingerprint
    assert answer["tls"] is True and answer["token_required"] is False
    assert answer["fingerprint"] == fingerprint(os.path.join(tmp, "certs", "ca.crt"))
    # the key never leaves: only public facts are in the answer
    assert b"PRIVATE" not in ask([REQUEST])[0]


def test_anything_else_is_ignored(tmp):
    use_server_config(tmp)
    junk = [
        b"hello",
        b"\xff\xfe not utf-8",
        json.dumps({"type": "pyhome-server", "version": 1}).encode(),
        json.dumps({"type": "pyhome-discover"}).encode(),
        json.dumps(["pyhome-discover", 1]).encode(),
        json.dumps({"type": "pyhome-discover", "version": 1, "pad": "x" * 3000}).encode(),
    ]
    assert ask(junk) == []


def test_at_most_twenty_answers_a_second(tmp):
    use_server_config(tmp)
    assert len(ask([REQUEST] * 35)) == discovery.RATE


def test_rate_frees_up_after_a_second(tmp):
    protocol = discovery.DiscoveryProtocol({"type": "pyhome-server"}, rate=2)

    class Transport:
        sent = 0

        def sendto(self, data, addr):
            Transport.sent += 1

    protocol.connection_made(Transport())
    for _ in range(5):
        protocol.datagram_received(REQUEST, ("127.0.0.1", 1))
    assert Transport.sent == 2
    # a second later the oldest answers no longer count
    protocol.sent = type(protocol.sent)(t - 1.1 for t in protocol.sent)
    protocol.datagram_received(REQUEST, ("127.0.0.1", 1))
    assert Transport.sent == 3


def test_discovery_port_and_switching_it_off(tmp):
    use_server_config(tmp)
    assert discovery.discovery_port() == 50002
    use_server_config(tmp, DISCOVERY_PORT=50555)
    assert discovery.discovery_port() == 50555
    use_server_config(tmp, DISCOVERY=False)
    assert discovery.discovery_port() is None
