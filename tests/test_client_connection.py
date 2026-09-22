"""Client handshake and connect loop against a fake server in this process."""
import asyncio
import contextlib
import io
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "client"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from shared.protocol import read_message, send_message  # noqa: E402
from handlers import connection_handler, message_handler  # noqa: E402
from handlers.commands import reconnect  # noqa: E402
from helpers import run_tests  # noqa: E402

WELCOME = {"type": "welcome", "id": "s", "name": "Server", "role": "server",
           "version": "test", "host": "127.0.0.1", "port": 1}
DENIED = {"type": "denied", "reason": "wrong token"}


class FakeServer:
    """Answers every hello with self.reply and records what arrived."""

    def __init__(self, reply):
        self.reply = reply
        self.hellos = []
        self.hung_up = 0
        self.writers = []

    async def handle(self, reader, writer):
        self.writers.append(writer)
        hello = await read_message(reader)
        self.hellos.append(hello)
        reply = dict(self.reply)
        await send_message(writer, reply.pop("type"), **reply)
        # wait until the client hangs up
        await reader.read()
        self.hung_up += 1
        writer.close()

    async def start(self, port=0):
        # rebinding the port right after a previous listener on it closed can
        # briefly fail on Windows, so give it a moment rather than change app code
        for attempt in range(20):
            try:
                self.server = await asyncio.start_server(self.handle, "127.0.0.1", port)
                break
            except OSError:
                if attempt == 19:
                    raise
                await asyncio.sleep(0.1)
        return self.server.sockets[0].getsockname()[1]

    async def kill(self):
        """Simulate the server going down: close every accepted client, then stop listening.

        Writers must close before wait_closed(), which since Python 3.12 also
        waits for accepted connections to finish; closing the listener first
        would deadlock against a still open connection.
        """
        for writer in self.writers:
            writer.close()
        self.server.close()
        await self.server.wait_closed()


def use_client_config(tmp, port, **values):
    path = os.path.join(tmp, "client.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "c", "NAME": "Client", "TYPE": "client", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": port, **values}, f)
    config.init(tmp, path)
    return path


def reset():
    c = connection_handler.connection
    c.connected = False
    c.reader = None
    c.writer = None
    c.server_info = {}
    c.auto_reconnect = False
    # a lock binds to the first event loop that waits on it, and every test runs its own loop
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


def test_hello_carries_the_token(tmp):
    reset()

    async def scenario():
        server = FakeServer(WELCOME)
        use_client_config(tmp, await server.start(), TOKEN="s3cret")
        await connection_handler.handshake()
        assert connection_handler.connection.connected
        await hang_up()
        return server.hellos[0]

    hello, out = quietly(scenario())
    assert hello["token"] == "s3cret", hello
    assert "s3cret" not in out, "the client must not print its token"


def test_no_token_sends_null(tmp):
    reset()

    async def scenario():
        server = FakeServer(WELCOME)
        use_client_config(tmp, await server.start())
        await connection_handler.handshake()
        await hang_up()
        return server.hellos[0]

    hello, _ = quietly(scenario())
    assert "token" in hello and hello["token"] is None, hello


def test_numeric_token_is_sent_as_string(tmp):
    reset()

    async def scenario():
        server = FakeServer(WELCOME)
        use_client_config(tmp, await server.start(), TOKEN=12345)
        await connection_handler.handshake()
        await hang_up()
        return server.hellos[0]

    hello, _ = quietly(scenario())
    assert hello["token"] == "12345", hello


def test_denied_raises_and_closes(tmp):
    reset()

    async def scenario():
        server = FakeServer(DENIED)
        use_client_config(tmp, await server.start(), TOKEN="guess")
        try:
            await connection_handler.handshake()
        except connection_handler.AccessDenied as e:
            reason = str(e)
        else:
            raise AssertionError("expected AccessDenied")
        # the half open socket is closed, the server sees the hang up
        await until(lambda: server.hung_up == 1)
        return reason

    reason, _ = quietly(scenario())
    assert reason == "wrong token", reason
    assert not connection_handler.connection.connected


def test_denied_stops_retrying(tmp):
    reset()

    async def scenario():
        server = FakeServer(DENIED)
        use_client_config(tmp, await server.start(), TOKEN="guess")
        loop = asyncio.create_task(connection_handler.connect_to_server_async())
        await until(lambda: server.hellos)
        # well past the loop's one second idle tick
        await asyncio.sleep(2.5)
        loop.cancel()
        return len(server.hellos)

    attempts, out = quietly(scenario())
    assert attempts == 1, f"retried {attempts} times with the same token"
    assert connection_handler.connection.auto_reconnect is False
    assert "wrong token" in out and "reconnect" in out, out


def test_reconnect_uses_the_corrected_token(tmp):
    reset()

    async def scenario():
        server = FakeServer(DENIED)
        path = use_client_config(tmp, await server.start(), TOKEN="guess")
        loop = asyncio.create_task(connection_handler.connect_to_server_async())
        await until(lambda: server.hellos)

        # the user fixes the file and types reconnect, no restart
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["TOKEN"] = "s3cret"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        server.reply = WELCOME
        await reconnect.function()

        await until(lambda: connection_handler.connection.connected)
        loop.cancel()
        await hang_up()
        return server.hellos[-1]

    hello, _ = quietly(scenario())
    assert hello["token"] == "s3cret", hello


def test_unexpected_error_keeps_retrying(tmp):
    reset()
    calls = []

    async def broken_handshake():
        calls.append(1)
        raise RuntimeError("surprise")

    original = (connection_handler.handshake, connection_handler.RETRY_SECONDS)
    connection_handler.handshake = broken_handshake
    connection_handler.RETRY_SECONDS = 0.05
    try:
        async def scenario():
            loop = asyncio.create_task(connection_handler.connect_to_server_async())
            await until(lambda: len(calls) >= 3)
            loop.cancel()

        quietly(scenario())
    finally:
        connection_handler.handshake, connection_handler.RETRY_SECONDS = original
    assert connection_handler.connection.auto_reconnect is True


def test_server_restart_is_noticed_once_and_reconnects(tmp):
    reset()

    async def scenario():
        server = FakeServer(WELCOME)
        port = await server.start()
        use_client_config(tmp, port)

        original_retry = connection_handler.RETRY_SECONDS
        connection_handler.RETRY_SECONDS = 0.2
        connect_task = asyncio.create_task(connection_handler.connect_to_server_async())
        receive_task = asyncio.create_task(message_handler.receive_messages_async())
        new_server = None
        try:
            await until(lambda: connection_handler.connection.connected)

            # take the server down under the live client
            await server.kill()
            await asyncio.sleep(1.5)

            # a new server takes its place on the same port, the client should find it
            new_server = FakeServer(WELCOME)
            await new_server.start(port)

            await until(lambda: connection_handler.connection.connected, seconds=10)

            return list(new_server.hellos)
        finally:
            connection_handler.RETRY_SECONDS = original_retry
            connect_task.cancel()
            receive_task.cancel()
            for task in (connect_task, receive_task):
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            # hang up the client before killing the second server, closing the
            # listener first would deadlock against the still open connection
            await hang_up()
            if new_server is not None:
                await new_server.kill()

    hellos, out = quietly(scenario())
    assert len(hellos) == 1, "the second server should get exactly one hello"
    assert out.count("Connection closed by server") == 1, out


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
