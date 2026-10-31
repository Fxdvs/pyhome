"""Asks the network which pyhome servers are there: the launcher's side of discovery.

A request goes to the broadcast address of the networks this computer is on
and to 127.0.0.1; every server that hears it answers (server/handlers/discovery.py).
An answer says who the server is, never its token. Nothing in it is proof:
with TLS, the fingerprint is shown so it can be compared with the one the
server prints, and a ca.crt fetched from the server must match it.
"""
import hashlib
import ipaddress
import json
import socket
import ssl
import time
import urllib.request

from launcher import core  # noqa: F401, puts the repo root on the path for shared
from shared.network import get_local_ip

DEFAULT_PORT = 50002
REQUEST = json.dumps({"type": "pyhome-discover", "version": 1}).encode("utf-8")
# an answer larger than this is not one
MAX_SIZE = 2048
PORTS = range(1, 65536)
# what a server's /ca.crt may be at most; a certificate is about 700 bytes
CA_LIMIT = 65536


def local_addresses():
    """The IPv4 addresses this computer has on its networks, loopback excepted."""
    found = {get_local_ip()}
    try:
        found.update(info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    return sorted(a for a in found if not a.startswith("127."))


def targets():
    """Where the request goes: everyone on the local segment, each network's broadcast, this computer.

    A network is taken as /24, which home networks are; a wider one still
    hears the request through 255.255.255.255 on the main interface.
    """
    hosts = ["255.255.255.255"]
    for address in local_addresses():
        hosts.append(str(ipaddress.ip_network(f"{address}/24", strict=False).broadcast_address))
    hosts.append("127.0.0.1")
    return list(dict.fromkeys(hosts))


def parse_answer(data):
    """The answer as a dict of its known fields, or None when it is not a server's answer."""
    if len(data) > MAX_SIZE:
        return None
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(message, dict) or message.get("type") != "pyhome-server" or message.get("version") != 1:
        return None
    answer = {key: message.get(key) for key in
              ("id", "name", "port", "web_port", "tls", "fingerprint", "token_required")}
    if not isinstance(answer["id"], str) or not answer["id"]:
        return None
    if not isinstance(answer["name"], str):
        answer["name"] = answer["id"]
    for key in ("port", "web_port"):
        # bool is an int in python, and no port
        if type(answer[key]) is not int or answer[key] not in PORTS:
            return None
    if not isinstance(answer["tls"], bool) or not isinstance(answer["token_required"], bool):
        return None
    if answer["tls"] != isinstance(answer["fingerprint"], str):
        # TLS comes with a fingerprint, plain text without one
        return None
    return answer


def find_servers(port=DEFAULT_PORT, timeout=1.0, hosts=None):
    """Every server that answers within timeout seconds, one entry per server.

    Each entry is the answer plus "addresses" it answered from and "host",
    the one to use: a network address over 127.0.0.1, so a config made with
    it also works on another computer.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            # windows: an address nobody listens on would end the reading below
            sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        sock.bind(("0.0.0.0", 0))
        for host in hosts or targets():
            try:
                sock.sendto(REQUEST, (host, port))
            except OSError:
                # a network that cannot broadcast; the others still can
                pass

        found = {}
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            sock.settimeout(left)
            try:
                data, (address, _) = sock.recvfrom(65535)
            except socket.timeout:
                break
            except OSError:
                continue
            answer = parse_answer(data)
            if answer is None:
                continue
            key = (answer["id"], answer["port"], answer["fingerprint"])
            entry = found.setdefault(key, {**answer, "addresses": []})
            if address not in entry["addresses"]:
                entry["addresses"].append(address)
    finally:
        sock.close()

    servers = list(found.values())
    for server in servers:
        outside = [a for a in server["addresses"] if not a.startswith("127.")]
        server["host"] = (outside or server["addresses"])[0]
    return sorted(servers, key=lambda s: (s["name"].lower(), s["host"]))


def ca_fingerprint(pem):
    """SHA-256 of a PEM certificate as AB:CD:..., the same as the server and make_certs.py print."""
    return ":".join(f"{b:02X}" for b in hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).digest())


class CAError(Exception):
    """The server's ca.crt could not be fetched, or is not the one its answer named."""


def fetch_ca(host, web_port, expected, timeout=5):
    """The server's ca.crt from its dashboard, as PEM text, checked against the fingerprint expected.

    The download itself cannot be verified, that is what the authority is for;
    the fingerprint is the check. Not through any proxy: the server is at home.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(f"https://{host}:{web_port}/ca.crt", timeout=timeout) as response:
            pem = response.read(CA_LIMIT).decode("ascii")
        actual = ca_fingerprint(pem)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        raise CAError(f"ca.crt sa nedá stiahnuť zo servera {host}:{web_port}: {e}") from e
    if actual != expected:
        raise CAError("ca.crt zo servera nemá odtlačok, ktorý server ohlásil. Neukladám ho.")
    return pem
