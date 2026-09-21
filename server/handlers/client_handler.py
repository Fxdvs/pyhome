import json
import os
import asyncio

from shared.colors import GRAY, GREEN, RED, RESET
from shared.config import get_config
from shared.console import print_message
from shared.protocol import (
    HELLO,
    MESSAGE,
    WELCOME,
    ProtocolError,
    read_message,
    send_message,
)

HANDSHAKE_TIMEOUT = 10

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_FILE = os.path.join(BASE_DIR, "data", "clients.json")

# read at call time, so a renamed server is sent to clients right away
def get_server_info():
    return {
        "id": get_config("ID"),
        "name": get_config("NAME"),
        # not "type", that name belongs to the message envelope
        "device_type": get_config("TYPE"),
        "version": get_config("VERSION"),
        "host": get_config("HOST"),
        "port": get_config("PORT"),
    }

# global vars
connected_clients = {}
clients_lock = asyncio.Lock()

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

        # store client
        async with clients_lock:
            connected_clients[addr] = {
                "name": client_name,
                "id": client_id,
                "writer": writer
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

            if message["type"] == MESSAGE:
                text = message.get("text", "")
                print_message(f"From client {GREEN}{label}{RESET}: {text}")
            else:
                print_message(f"{GRAY}Ignored '{message['type']}' from {label}{RESET}")

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        pass

    except ProtocolError as e:
        print_message(f"Client {RED}{addr}{RESET} spoke badly: {e}")

    except Exception as e:
        print_message(f"Client {RED}{addr}@{client_name}#{client_id}{RESET} had a fatal error: {e}")

    finally:
        # remove client
        async with clients_lock:
            if addr in connected_clients:
                client_info = connected_clients[addr]
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} has disconnected")
                del connected_clients[addr]

        writer.close()
        await writer.wait_closed()

def save_client(addr, client_name, client_id):
    client_data = {"ID": client_id, "NAME": client_name}
    clients = []
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
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

    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=4)

# number of connected clients
def get_connected_clients():
    return connected_clients

# lock
def get_clients_lock():
    return clients_lock


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
