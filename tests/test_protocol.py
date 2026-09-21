"""shared/protocol.py: framing and the envelope rules."""
import asyncio
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from shared import protocol  # noqa: E402
from shared.protocol import ProtocolError, read_message, send_message  # noqa: E402
from helpers import run_tests  # noqa: E402


class FakeWriter:
    """Collects what send_message writes."""

    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data

    async def drain(self):
        pass


def read_all(chunks):
    """Feed chunks to a StreamReader and read messages until end of stream."""
    async def scenario():
        reader = asyncio.StreamReader()
        for chunk in chunks:
            reader.feed_data(chunk)
        reader.feed_eof()
        messages = []
        while True:
            message = await read_message(reader)
            if message is None:
                return messages
            messages.append(message)
    return asyncio.run(scenario())


def encode(*messages):
    return b"".join(json.dumps(m).encode("utf-8") + b"\n" for m in messages)


def test_new_message_types(tmp):
    assert protocol.CMD == "cmd"
    assert protocol.RESULT == "result"
    assert protocol.STATE == "state"


def test_several_messages_in_one_write(tmp):
    data = encode({"type": "msg", "text": "a"}, {"type": "msg", "text": "b"}, {"type": "state", "state": {}})
    messages = read_all([data])
    assert [m.get("text") for m in messages] == ["a", "b", None], messages


def test_message_split_across_writes(tmp):
    data = encode({"type": "msg", "text": "split in two"})
    messages = read_all([data[:7], data[7:]])
    assert messages == [{"type": "msg", "text": "split in two"}], messages


def test_large_message_in_many_chunks(tmp):
    # far larger than one read, still under the StreamReader line limit of 64 KiB
    text = "x" * 50000
    data = encode({"type": "msg", "text": text})
    chunks = [data[i:i + 1000] for i in range(0, len(data), 1000)]
    messages = read_all(chunks)
    assert len(messages) == 1 and messages[0]["text"] == text


def test_non_ascii_text_survives(tmp):
    messages = read_all([encode({"type": "msg", "text": "Kuchyňa ✔"})])
    assert messages[0]["text"] == "Kuchyňa ✔"


def test_send_message_writes_one_line(tmp):
    writer = FakeWriter()
    asyncio.run(send_message(writer, protocol.CMD, action="turn_on", params={}, request_id="ab12cd34"))
    assert writer.data.endswith(b"\n") and writer.data.count(b"\n") == 1
    assert json.loads(writer.data) == {"type": "cmd", "action": "turn_on", "params": {}, "request_id": "ab12cd34"}


def test_payload_cannot_be_called_type(tmp):
    try:
        asyncio.run(send_message(FakeWriter(), protocol.STATE, type="light"))
    except ProtocolError:
        return
    raise AssertionError("expected ProtocolError")


def test_message_without_type_is_rejected(tmp):
    try:
        read_all([b'{"text": "no type"}\n'])
    except ProtocolError:
        return
    raise AssertionError("expected ProtocolError")


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
