"""End to end: v1.2 Part 2 "Done when", TLS between real processes, read off the wire."""
import os
import socket
import sys
import threading

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))

from e2e import free_port, wait_for, with_system  # noqa: E402
import make_certs  # noqa: E402

TOKEN = "s3cret-on-the-wire"


class Tap:
    """A TCP proxy between a client and the server that keeps every byte the client sends."""

    def __init__(self, upstream_port):
        self.upstream_port = upstream_port
        self.port = free_port()
        self.seen = bytearray()
        self.lock = threading.Lock()
        self.listener = socket.create_server(("127.0.0.1", self.port))
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(("127.0.0.1", self.upstream_port))
            threading.Thread(target=self.pump, args=(client, upstream, True), daemon=True).start()
            threading.Thread(target=self.pump, args=(upstream, client, False), daemon=True).start()

    def pump(self, source, target, record):
        try:
            while data := source.recv(65536):
                if record:
                    with self.lock:
                        self.seen += data
                target.sendall(data)
        except OSError:
            pass
        finally:
            for s in (source, target):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def wire(self):
        with self.lock:
            return bytes(self.seen)

    def close(self):
        self.listener.close()


def make(tmp):
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost", "127.0.0.1"])


def test_tls_hides_the_token(tmp):
    def scenario(system):
        make(system.tmp)
        system.start_server(TOKEN=TOKEN, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
        tap = Tap(system.port)
        try:
            system.start_client("e2e-light", "light", TOKEN=TOKEN, TLS_CA="certs/ca.crt", PORT=tap.port)
            wait_for(lambda: system.client("e2e-light"), "the light over TLS")
            wait_for(lambda: len(tap.wire()) > 200, "bytes on the wire")
            wire = tap.wire()
            assert TOKEN.encode() not in wire, "the token crossed the wire in plain text"
            assert b'"hello"' not in wire, "the protocol is readable on the wire"
            assert wire[:1] == b"\x16", "the first byte is a TLS handshake record"
        finally:
            tap.close()

        assert "TLS on, certificate valid until" in system.log("server")
        assert "No TLS_CERT set" not in system.log("server")
        assert "(TLS)" in system.log("e2e-light") and "No TLS_CA set" not in system.log("e2e-light")
        assert TOKEN not in system.log("server") and TOKEN not in system.log("e2e-light")

    with_system(tmp, scenario)


def test_plain_text_shows_the_token(tmp):
    """The control: the same tap does see the token when nothing is encrypted."""
    def scenario(system):
        system.start_server(TOKEN=TOKEN)
        tap = Tap(system.port)
        try:
            system.start_client("e2e-light", "light", TOKEN=TOKEN, PORT=tap.port)
            wait_for(lambda: TOKEN.encode() in tap.wire(), "the token on the wire")
        finally:
            tap.close()
        assert "No TLS_CERT set" in system.log("server")
        assert "No TLS_CA set" in system.log("e2e-light")

    with_system(tmp, scenario)


def test_client_trusting_another_authority_is_refused(tmp):
    def scenario(system):
        make(system.tmp)
        make_certs.make_certs(os.path.join(system.tmp, "other"), ["localhost"])
        system.start_server(TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
        system.start_client("e2e-good", "light", TLS_CA="certs/ca.crt")
        system.start_client("e2e-bad", "light", TLS_CA="other/ca.crt")
        system.start_client("e2e-plain", "light")

        wait_for(lambda: system.client("e2e-good"), "the trusting client")
        wait_for(lambda: "not trusted by TLS_CA" in system.log("e2e-bad"), "the refusal")
        assert "reconnect" in system.log("e2e-bad")
        wait_for(lambda: "If it uses TLS, set TLS_CA" in system.log("e2e-plain"), "the plain client's hint")
        assert system.client("e2e-bad") is None and system.client("e2e-plain") is None

    with_system(tmp, scenario)


def test_server_with_a_missing_certificate_does_not_start(tmp):
    def scenario(system):
        process = system.start("server", os.path.join(ROOT_DIR, "server"), {
            "ID": "e2e-server", "NAME": "E2E server", "TYPE": "server", "VERSION": "test",
            "HOST": "127.0.0.1", "PORT": system.port, "WEB_HOST": "127.0.0.1", "WEB_PORT": system.web_port,
            "TLS_CERT": "certs/server.crt", "TLS_KEY": "certs/server.key",
        }, stdin=__import__("subprocess").PIPE)
        # the fatal branch waits for Enter, give it one
        process.stdin.write(b"\n")
        process.stdin.flush()
        process.wait(timeout=30)
        assert process.returncode != 0
        assert "TLS file not found" in system.log("server"), system.log("server")

    with_system(tmp, scenario)
