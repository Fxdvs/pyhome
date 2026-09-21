import asyncio

from shared.colors import GRAY, GREEN, RED, RESET
from shared.console import print_message
from shared.protocol import MESSAGE, ProtocolError, read_message
from handlers.connection_handler import connection

# how often the receive loop wakes up to notice a disconnect
READ_TIMEOUT = 0.5


async def receive_messages_async():
    while True:
        try:
            if not connection.connected or connection.reader is None:
                await asyncio.sleep(READ_TIMEOUT)
                continue

            try:
                message = await asyncio.wait_for(
                    read_message(connection.reader), timeout=READ_TIMEOUT
                )
            except asyncio.TimeoutError:
                # nothing arrived, the half read line stays in the buffer
                continue

            # None means the server closed the connection
            if message is None:
                handle_drop("Connection closed by server")
                continue

            handle_message(message)

        except ProtocolError as e:
            print_message(f"{RED}Bad message from server{RESET}: {e}")

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            handle_drop("Connection lost")

        except Exception as e:
            handle_drop(f"Error receiving: {e}")
            await asyncio.sleep(1)


def handle_message(message):
    if message["type"] == MESSAGE:
        text = message.get("text", "")
        print_message(f"from {GREEN}{connection.label}{RESET} {text}")
    else:
        print_message(f"{GRAY}Ignored message of type '{message['type']}'{RESET}")


def handle_drop(reason):
    """Mark the connection as dead and let the connection handler reconnect."""
    # the disconnect command already cleared the flag, so this drop was intentional
    if not connection.connected:
        return

    connection.detach()
    connection.auto_reconnect = True
    print_message(reason)
