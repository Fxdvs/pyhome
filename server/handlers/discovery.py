"""Answers who is there: a UDP datagram asks, the server says who it is and how to reach it.

The launcher's Find servers broadcasts {"type": "pyhome-discover", "version": 1}
and every server that hears it answers the sender with its id, name, ports,
whether it has TLS and the fingerprint of its ca.crt. Never the token, and
nothing else that is secret: anyone on the network may ask. The address is
the one the answer comes from, so the server never has to know its own.
"""
import asyncio
import collections
import json
import socket
import time

from shared.config import get_config
from handlers.tls import TLSConfigError, ca_file, fingerprint, tls_files

DEFAULT_PORT = 50002
REQUEST = "pyhome-discover"
ANSWER = "pyhome-server"
VERSION = 1
# a request larger than this is not one, and is not read further
MAX_SIZE = 2048
# answers per second at most, so the server cannot be used to flood the network
RATE = 20


def discovery_port():
    """The UDP port to answer on, or None when DISCOVERY is false."""
    if get_config("DISCOVERY", True) is False:
        return None
    return get_config("DISCOVERY_PORT", DEFAULT_PORT)


def server_answer():
    """What the server says about itself. Public on purpose: no token, nothing secret."""
    try:
        tls = tls_files() is not None
        ca = ca_file()
    except TLSConfigError:
        tls, ca = False, None
    return {
        "type": ANSWER,
        "version": VERSION,
        "id": get_config("ID"),
        "name": get_config("NAME"),
        "port": get_config("PORT"),
        "web_port": get_config("WEB_PORT", 50001),
        "tls": tls,
        "fingerprint": fingerprint(ca) if ca else None,
        "token_required": bool(get_config("TOKEN")),
    }


def is_request(data):
    """True when data is a discovery request: small, JSON, the right type."""
    if len(data) > MAX_SIZE:
        return False
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False
    return isinstance(message, dict) and message.get("type") == REQUEST and isinstance(message.get("version"), int)


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, answer, rate=RATE):
        self.answer = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        self.rate = rate
        # when the answers of the last second went out
        self.sent = collections.deque()
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not is_request(data):
            return
        now = time.monotonic()
        while self.sent and now - self.sent[0] >= 1:
            self.sent.popleft()
        if len(self.sent) >= self.rate:
            return
        self.sent.append(now)
        self.transport.sendto(self.answer, addr)

    def error_received(self, exc):
        # an asker that is gone again; nothing to do
        pass


def discovery_socket(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # windows reports an asker that went away as an error on the next read, which would
    # end reading altogether; this turns that report off
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        sock.ioctl(socket.SIO_UDP_CONNRESET, False)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    return sock


async def start_discovery(port):
    """Answer on UDP port. Returns the transport to close. OSError when the port cannot be used."""
    loop = asyncio.get_running_loop()
    sock = discovery_socket(get_config("HOST", "0.0.0.0"), port)
    transport, _ = await loop.create_datagram_endpoint(lambda: DiscoveryProtocol(server_answer()), sock=sock)
    return transport
