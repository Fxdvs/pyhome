"""Client side of TLS: the handshake against a fake TLS server, and every way the two sides can disagree."""
import asyncio
import contextlib
import io
import json
import os
import ssl
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "client"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from shared.protocol import read_message, send_message  # noqa: E402
from handlers import connection_handler  # noqa: E402
from handlers.commands import reconnect  # noqa: E402
from helpers import run_tests  # noqa: E402

# make_certs lives with the server, the client itself never imports it
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
import make_certs  # noqa: E402

WELCOME = {"type": "welcome", "id": "s", "name": "Server", "role": "server",
           "version": "test", "host": "127.0.0.1", "port": 1}


class FakeServer:
    """Answers every hello with a welcome, over TLS when given a context."""

    def __init__(self, context=None):
        self.context = context
        self.hellos = []
        self.writers = []

    async def handle(self, reader, writer):
        self.writers.append(writer)
        try:
            hello = await read_message(reader)
        except Exception:
            # what a plain server makes of a TLS hello
            writer.close()
            return
        if hello is None:
            writer.close()
            return
        self.hellos.append(hello)
        reply = dict(WELCOME)
        await send_message(writer, reply.pop("type"), **reply)
        await reader.read()
        writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0, ssl=self.context)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        for writer in self.writers:
            writer.close()
        self.server.close()
        await self.server.wait_closed()


def certs(tmp, name="certs"):
    """A fresh authority and server certificate in tmp/name. Returns the server's SSLContext."""
    folder = os.path.join(tmp, name)
    make_certs.make_certs(folder, ["localhost", "127.0.0.1"])
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(os.path.join(folder, "server.crt"), os.path.join(folder, "server.key"))
    return context


def use_client_config(tmp, port, **values):
    path = os.path.join(tmp, "client.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "c", "NAME": "Client", "TYPE": "client", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": port, "TOKEN": "s3cret", **values}, f)
    config.init(tmp, path)
    return path


def reset():
    c = connection_handler.connection
    c.connected = False
    c.reader = None
    c.writer = None
    c.server_info = {}
    c.auto_reconnect = False
    c.tls = False
    c.lock = asyncio.Lock()


async def until(check, seconds=5):
    for _ in range(int(seconds * 20)):
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition never became true")


async def hang_up():
    writer = connection_handler.connection.detach()
    if writer:
        writer.close()


def quietly(coroutine):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = asyncio.run(coroutine)
    return result, out.getvalue()


def expect(coroutine, error):
    """The message of the error coroutine raises, run quietly."""
    async def wrapped():
        try:
            await coroutine
        except error as e:
            return str(e)
        raise AssertionError(f"expected {error.__name__}")
    return quietly(wrapped())[0]


def test_tls_handshake(tmp):
    reset()
    server_context = certs(tmp)

    async def scenario():
        server = FakeServer(server_context)
        use_client_config(tmp, await server.start(), TLS_CA="certs/ca.crt")
        await connection_handler.handshake()
        tls = connection_handler.connection.tls
        await hang_up()
        await server.stop()
        return tls, server.hellos[0]

    (tls, hello), out = quietly(scenario())
    assert tls is True and hello["token"] == "s3cret", hello
    assert "(TLS)" in out, out


def test_tls_ca_is_relative_to_the_config(tmp):
    reset()
    server_context = certs(tmp)
    # started from another folder, the path still resolves next to the config
    os.chdir(os.path.dirname(tmp))

    async def scenario():
        server = FakeServer(server_context)
        use_client_config(tmp, await server.start(), TLS_CA="certs/ca.crt")
        await connection_handler.handshake()
        await hang_up()
        await server.stop()

    quietly(scenario())


def test_untrusted_certificate_is_refused(tmp):
    reset()
    server_context = certs(tmp, "house")
    certs(tmp, "other")

    async def scenario():
        server = FakeServer(server_context)
        use_client_config(tmp, await server.start(), TLS_CA="other/ca.crt")
        try:
            return await connection_handler.handshake()
        finally:
            await server.stop()

    message = expect(scenario(), connection_handler.TLSRefused)
    assert message.startswith("server certificate not trusted by TLS_CA:"), message
    assert not connection_handler.connection.connected


def test_untrusted_certificate_stops_retrying(tmp):
    reset()
    server_context = certs(tmp, "house")
    certs(tmp, "other")
    attempts = []
    # a failed TLS handshake never reaches the server's handler, count on the client
    original = connection_handler.handshake

    async def counting():
        attempts.append(1)
        await original()

    async def scenario():
        server = FakeServer(server_context)
        use_client_config(tmp, await server.start(), TLS_CA="other/ca.crt")
        loop = asyncio.create_task(connection_handler.connect_to_server_async())
        await until(lambda: attempts)
        # well past the loop's one second idle tick
        await asyncio.sleep(2.5)
        loop.cancel()
        await server.stop()

    connection_handler.handshake = counting
    try:
        _, out = quietly(scenario())
    finally:
        connection_handler.handshake = original
    assert len(attempts) == 1, f"retried {len(attempts)} times with the same TLS_CA"
    assert connection_handler.connection.auto_reconnect is False
    assert "TLS refused" in out and "not trusted" in out and "reconnect" in out, out


def test_missing_tls_ca_file(tmp):
    reset()
    use_client_config(tmp, 1, TLS_CA="certs/nope.crt")
    message = expect(connection_handler.handshake(), connection_handler.TLSRefused)
    assert message == f"TLS_CA file not found: {os.path.join(tmp, 'certs', 'nope.crt')}", message


def test_tls_ca_that_is_not_a_certificate(tmp):
    reset()
    with open(os.path.join(tmp, "junk.crt"), "w", encoding="utf-8") as f:
        f.write("not a certificate\n")
    use_client_config(tmp, 1, TLS_CA="junk.crt")
    message = expect(connection_handler.handshake(), connection_handler.TLSRefused)
    assert message.startswith("TLS_CA is not a certificate"), message


def test_plain_client_to_a_tls_server(tmp):
    reset()
    server_context = certs(tmp)

    async def scenario():
        server = FakeServer(server_context)
        use_client_config(tmp, await server.start())
        try:
            return await connection_handler.handshake()
        finally:
            await server.stop()

    message = expect(scenario(), ConnectionError)
    assert "server closed the connection during the handshake" in message, message
    assert "If it uses TLS, set TLS_CA in" in message, message


def test_tls_client_to_a_plain_server(tmp):
    reset()
    certs(tmp)
    original = connection_handler.HANDSHAKE_TIMEOUT
    connection_handler.HANDSHAKE_TIMEOUT = 1

    async def scenario():
        server = FakeServer()
        use_client_config(tmp, await server.start(), TLS_CA="certs/ca.crt")
        try:
            return await connection_handler.handshake()
        finally:
            await server.stop()

    try:
        message = expect(scenario(), ConnectionError)
    finally:
        connection_handler.HANDSHAKE_TIMEOUT = original
    assert message.startswith("TLS handshake failed: "), message
    assert "If the server does not use TLS, empty TLS_CA in" in message, message


def test_server_down_is_not_a_tls_problem(tmp):
    reset()
    certs(tmp)

    async def free_port():
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        return port

    port = asyncio.run(free_port())
    use_client_config(tmp, port, TLS_CA="certs/ca.crt")
    message = expect(connection_handler.handshake(), OSError)
    assert "TLS" not in message, message


def test_reconnect_picks_up_a_fixed_tls_ca(tmp):
    reset()
    server_context = certs(tmp, "house")
    certs(tmp, "other")

    async def scenario():
        server = FakeServer(server_context)
        path = use_client_config(tmp, await server.start(), TLS_CA="other/ca.crt")
        loop = asyncio.create_task(connection_handler.connect_to_server_async())
        await until(lambda: connection_handler.connection.auto_reconnect is False and "TLS refused" in out.getvalue())

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["TLS_CA"] = "house/ca.crt"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        await reconnect.function()

        await until(lambda: connection_handler.connection.connected)
        loop.cancel()
        tls = connection_handler.connection.tls
        await hang_up()
        await server.stop()
        return tls

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        tls = asyncio.run(scenario())
    assert tls is True


def test_tls_warning(tmp):
    use_client_config(tmp, 1)
    assert connection_handler.tls_warning() == \
        "No TLS_CA set, the token and every message cross the network in plain text"
    use_client_config(tmp, 1, TLS_CA="certs/ca.crt")
    assert connection_handler.tls_warning() is None


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
