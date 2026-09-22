import json
import os
import asyncio
import hmac
from uuid import uuid4

from shared.colors import GRAY, GREEN, RED, RESET
from shared.config import get_config, get_config_path
from shared.console import print_message
from shared.protocol import (
    CMD,
    DENIED,
    HELLO,
    MESSAGE,
    RESULT,
    STATE,
    WELCOME,
    ProtocolError,
    read_message,
    send_message,
)

HANDSHAKE_TIMEOUT = 10
# how long do waits for a client to answer a cmd
COMMAND_TIMEOUT = 5


def get_clients_file():
    """clients.json next to the config in use, so a server started with --config keeps its own list."""
    return os.path.join(os.path.dirname(get_config_path()), "clients.json")

# read at call time, so a renamed server is sent to clients right away
def get_server_info():
    return {
        "id": get_config("ID"),
        "name": get_config("NAME"),
        # the config's TYPE, not "type", that name belongs to the message envelope
        "role": get_config("TYPE"),
        "version": get_config("VERSION"),
        "host": get_config("HOST"),
        "port": get_config("PORT"),
    }

# global vars
connected_clients = {}
clients_lock = asyncio.Lock()

# request_id -> (addr of the client asked, future the result completes)
pending_requests = {}


def clean_capabilities(value):
    """The client's action names. Anything that is not a list of strings is dropped."""
    if not isinstance(value, list):
        return []
    return [name for name in value if isinstance(name, str)]


def clean_device(value):
    """The client's device name. Anything but a non-empty string is dropped."""
    if isinstance(value, str) and value:
        return value
    return None


def check_token(hello):
    """None when the client may stay, otherwise the reason it is refused."""
    expected = get_config("TOKEN")
    # no token on the server keeps every existing client working after an upgrade
    if not expected:
        return None

    given = hello.get("token")
    if not isinstance(given, str) or not given:
        return "this server needs a token, set TOKEN in the client's config"

    # compare_digest takes as long for a near miss as for a wild guess
    if not hmac.compare_digest(given.encode("utf-8"), str(expected).encode("utf-8")):
        return "wrong token"
    return None


def token_warning():
    """The startup warning for a server that lets everyone in, or None."""
    if get_config("TOKEN"):
        return None
    return "No TOKEN set, every client that can reach this server is accepted"


async def handle_client_async(reader, writer):
    addr = writer.get_extra_info('peername')
    client_name = None
    client_id = None

    try:
        # the client introduces itself first
        hello = await asyncio.wait_for(read_message(reader), timeout=HANDSHAKE_TIMEOUT)

        if hello is None:
            writer.close()
            await writer.wait_closed()
            return

        if hello["type"] != HELLO:
            raise ProtocolError(f"expected '{HELLO}', got '{hello['type']}'")

        client_id = hello.get("id", "unknown")
        client_name = hello.get("name", "unknown")

        # refuse before the client is registered or saved, and never print the token
        reason = check_token(hello)
        if reason is not None:
            print_message(f"Refused {RED}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET}: {reason}")
            await send_message(writer, DENIED, reason=reason)
            return

        # store client
        async with clients_lock:
            connected_clients[addr] = {
                "name": client_name,
                "id": client_id,
                "writer": writer,
                "device": clean_device(hello.get("device")),
                "capabilities": clean_capabilities(hello.get("capabilities")),
                # only in memory, the client can be asked again after a restart
                "last_state": None,
            }

        save_client(addr, client_name, client_id)
        print_message(f"Client {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET} has connected")

        # send information about server
        await send_message(writer, WELCOME, **get_server_info())

        label = f"{addr[0]}:{addr[1]}@{client_name}#{client_id}"

        # receive messages
        while True:
            message = await read_message(reader)

            # None means the client closed the connection
            if message is None:
                break

            handle_message(addr, label, message)

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        pass

    except ProtocolError as e:
        print_message(f"Client {RED}{addr}{RESET} spoke badly: {e}")

    except Exception as e:
        print_message(f"Client {RED}{addr}@{client_name}#{client_id}{RESET} had a fatal error: {e}")

    finally:
        # nobody will answer them now, fail them instead of letting them time out
        fail_pending_requests(addr)
        # remove client
        async with clients_lock:
            if addr in connected_clients:
                client_info = connected_clients[addr]
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} has disconnected")
                del connected_clients[addr]

        writer.close()
        await writer.wait_closed()

def save_client(addr, client_name, client_id):
    clients_file = get_clients_file()
    client_data = {"ID": client_id, "NAME": client_name}
    clients = []
    if os.path.exists(clients_file):
        with open(clients_file, "r", encoding="utf-8") as f:
            try:
                clients = json.load(f)
            except json.JSONDecodeError:
                clients = []

    # update or add
    updated = False
    for i, c in enumerate(clients):
        if c.get("ID") == client_id:
            clients[i] = client_data
            updated = True
            break

    if not updated:
        clients.append(client_data)

    with open(clients_file, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=4)

# number of connected clients
def get_connected_clients():
    return connected_clients


def handle_message(addr, label, message):
    """One message from a client that finished the handshake."""
    message_type = message["type"]

    if message_type == MESSAGE:
        text = message.get("text", "")
        print_message(f"From client {GREEN}{label}{RESET}: {text}")

    elif message_type == RESULT:
        if not resolve_request(addr, message):
            print_message(f"{GRAY}Result from {label} that nobody is waiting for{RESET}")
        state = message.get("state")
        if message.get("ok") is True and isinstance(state, dict):
            connected_clients[addr]["last_state"] = state

    elif message_type == STATE:
        state = message.get("state")
        if isinstance(state, dict):
            connected_clients[addr]["last_state"] = state
            print_message(f"{GRAY}State from {label}: {json.dumps(state, ensure_ascii=False)}{RESET}")

    else:
        print_message(f"{GRAY}Ignored '{message_type}' from {label}{RESET}")


def resolve_request(addr, message):
    """Complete the request this result answers. False when nothing is waiting for it."""
    request_id = message.get("request_id")
    # a request_id we handed out is always a str; anything else cannot be a hit
    if not isinstance(request_id, str):
        return False
    entry = pending_requests.get(request_id)
    # an answer from another client, or to a request that already timed out
    if entry is None or entry[0] != addr or entry[1].done():
        return False
    entry[1].set_result(message)
    return True


def fail_pending_requests(addr):
    for request_addr, future in pending_requests.values():
        if request_addr == addr and not future.done():
            future.set_exception(ConnectionError("client disconnected"))


async def send_command(client_id, action, params, timeout=COMMAND_TIMEOUT):
    """Send cmd to the online client with this id and wait for its result.

    Returns the result message. Raises LookupError when no such client is
    online, asyncio.TimeoutError when it does not answer in time and
    ConnectionError when it disconnects first.
    """
    async with clients_lock:
        found = next(
            ((addr, info) for addr, info in connected_clients.items() if info["id"] == client_id),
            None,
        )
    if found is None:
        raise LookupError(f"no online client with id '{client_id}'")

    addr, info = found
    request_id = uuid4().hex[:8]
    future = asyncio.get_running_loop().create_future()
    pending_requests[request_id] = (addr, future)
    try:
        await send_message(info["writer"], CMD, action=action, params=params, request_id=request_id)
        return await asyncio.wait_for(future, timeout)
    finally:
        pending_requests.pop(request_id, None)


async def send_to_clients(target, text):
    """Send a message to one client id, or to every client when target is 'all'.

    Returns (delivered, failed) as lists of "name#id" labels.
    """
    async with clients_lock:
        # copy the matches out, so the lock is not held while writing
        recipients = [
            (addr, info) for addr, info in connected_clients.items()
            if target == "all" or info["id"] == target
        ]

    delivered = []
    failed = []

    for addr, info in recipients:
        label = f"{info['name']}#{info['id']}"
        try:
            await send_message(info["writer"], MESSAGE, text=text)
            delivered.append(label)
        except Exception as e:
            failed.append(f"{label} ({e})")

    return delivered, failed
