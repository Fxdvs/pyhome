import asyncio

from shared.colors import GRAY, GREEN, RED, RESET
from shared.console import print_message
from shared.protocol import CMD, MESSAGE, RESULT, ProtocolError, read_message
from handlers.connection_handler import connection, send_to_server
from handlers.device_handler import execute

# how often the receive loop wakes up to notice a disconnect
READ_TIMEOUT = 0.5

# commands in flight, asyncio keeps only a weak reference to a running task
_command_tasks = set()


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
    elif message["type"] == CMD:
        # its own task, so a slow action does not stall the receive loop
        task = asyncio.create_task(handle_command(message))
        _command_tasks.add(task)
        task.add_done_callback(_command_tasks.discard)
    else:
        print_message(f"{GRAY}Ignored message of type '{message['type']}'{RESET}")


async def handle_command(message):
    """Run the action and answer with a result carrying the same request_id."""
    action = message.get("action")
    params = message.get("params") or {}
    reply = await execute(action, params)

    if reply["ok"]:
        print_message(f"{GRAY}Ran {action} {params}{RESET}")
    else:
        print_message(f"{RED}Could not run {action}{RESET}: {reply['error']}")

    try:
        sent = await send_to_server(RESULT, request_id=message.get("request_id"), **reply)
    except OSError:
        sent = False
    if not sent:
        print_message(f"{RED}Result of {action} could not be sent{RESET}")


def handle_drop(reason):
    """Mark the connection as dead and let the connection handler reconnect."""
    # the disconnect command already cleared the flag, so this drop was intentional
    if not connection.connected:
        return

    connection.detach()
    connection.auto_reconnect = True
    print_message(reason)
