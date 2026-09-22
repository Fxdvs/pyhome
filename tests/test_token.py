"""Server side of the token: the check, the startup warning, refusing before registering."""
import asyncio
import contextlib
import io
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from shared import protocol  # noqa: E402
from shared.protocol import read_message, send_message  # noqa: E402
from handlers import client_handler  # noqa: E402
from helpers import run_tests  # noqa: E402

NEEDS_TOKEN = "this server needs a token, set TOKEN in the client's config"


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": 0, **values}, f)
    config.init(tmp, path)


def test_denied_type(tmp):
    assert protocol.DENIED == "denied"


def test_no_token_accepts_everyone(tmp):
    for values in ({}, {"TOKEN": ""}, {"TOKEN": None}):
        use_server_config(tmp, **values)
        for hello in ({}, {"token": "anything"}, {"token": None}, {"token": 5}):
            assert client_handler.check_token(hello) is None, (values, hello)


def test_right_token_is_accepted(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    assert client_handler.check_token({"token": "s3cret"}) is None


def test_wrong_token_is_refused(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    for token in ("guess", "s3cre", "s3cret ", "S3CRET"):
        assert client_handler.check_token({"token": token}) == "wrong token", token


def test_missing_token_is_refused(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    for hello in ({}, {"token": None}, {"token": ""}, {"token": 5}, {"token": ["s3cret"]}):
        assert client_handler.check_token(hello) == NEEDS_TOKEN, hello


def test_warning_only_without_token(tmp):
    use_server_config(tmp)
    assert client_handler.token_warning() == "No TOKEN set, every client that can reach this server is accepted"
    use_server_config(tmp, TOKEN="s3cret")
    assert client_handler.token_warning() is None


async def talk(port, hello):
    """Connect, send hello, return the first answer, or None if the server just closed."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        await send_message(writer, protocol.HELLO, **hello)
        answer = await asyncio.wait_for(read_message(reader), timeout=5)
        # after denied the server closes, reading again gives end of stream
        after = await asyncio.wait_for(read_message(reader), timeout=5) if answer and answer["type"] == "denied" else "open"
        return answer, after
    finally:
        writer.close()


def run_server(tmp, scenario, **values):
    use_server_config(tmp, **values)
    client_handler.connected_clients.clear()

    async def main():
        server = await asyncio.start_server(client_handler.handle_client_async, "127.0.0.1", 0)
        try:
            return await scenario(server.sockets[0].getsockname()[1])
        finally:
            server.close()

    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = asyncio.run(main())
    return result, out.getvalue()


def test_refused_client_is_not_registered(tmp):
    async def scenario(port):
        return await talk(port, {"id": "bad", "name": "Bad", "token": "guess"})

    (answer, after), out = run_server(tmp, scenario, TOKEN="s3cret")
    assert answer == {"type": "denied", "reason": "wrong token"}, answer
    assert after is None, "the server must close after denied"
    assert client_handler.connected_clients == {}
    assert not os.path.exists(os.path.join(tmp, "clients.json")), "a refused client must not be saved"
    assert "Refused" in out and "wrong token" in out, out
    assert "guess" not in out and "s3cret" not in out, "the token must never be printed"


def test_accepted_client_gets_welcome(tmp):
    async def scenario(port):
        answer, _ = await talk(port, {"id": "good", "name": "Good", "token": "s3cret"})
        return answer

    answer, out = run_server(tmp, scenario, TOKEN="s3cret")
    assert answer["type"] == "welcome", answer
    assert "token" not in answer, "welcome must not echo the token"
    with open(os.path.join(tmp, "clients.json"), encoding="utf-8") as f:
        assert [c["ID"] for c in json.load(f)] == ["good"]
    assert "s3cret" not in out


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
