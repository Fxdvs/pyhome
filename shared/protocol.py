"""Newline delimited JSON messages.

TCP is a stream of bytes, not of messages: two sends can arrive merged and
one send can arrive split. So every message is a single line of JSON ending
in "\\n", and the reader reads exactly one line at a time.

Every message is an object with a "type" field, the rest depends on the type.
"""
import json

# client -> server, first message on a new connection
HELLO = "hello"
# server -> client, answer to hello
WELCOME = "welcome"
# both ways, free text
MESSAGE = "msg"
# server -> client, run a device action
CMD = "cmd"
# client -> server, the answer to one cmd, matched by request_id
RESULT = "result"
# client -> server, device state sent unprompted
STATE = "state"
# server -> client, the hello was refused, the server closes after sending it
DENIED = "denied"


class ProtocolError(Exception):
    """The peer sent something that is not a valid message."""


async def send_message(writer, message_type, /, **payload):
    # message_type is positional only so that a payload field called
    # "message_type" cannot collide with it
    if "type" in payload:
        raise ProtocolError(
            "'type' is the envelope field, name the payload field something else"
        )

    line = json.dumps({"type": message_type, **payload}) + "\n"
    writer.write(line.encode("utf-8"))
    await writer.drain()


async def read_message(reader):
    """Read one message, or None when the peer closed the connection."""
    line = await reader.readline()

    # readline returns b"" only at end of stream, a blank line would be b"\n"
    if not line:
        return None

    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError(f"could not parse message: {e}") from e

    if not isinstance(message, dict) or "type" not in message:
        raise ProtocolError("message has no type")

    return message
