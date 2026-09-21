import asyncio
from shared.colors import GREEN, RESET
from handlers.connection_handler import (
    get_connection_state,
    set_connected,
    set_auto_reconnect,
)


async def receive_messages_async():
    while True:
        try:
            CONNECTED, reader, writer, server_info = get_connection_state()

            if not CONNECTED or reader is None:
                await asyncio.sleep(0.5)
                continue

            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            # empty read means the server closed the connection
            if not data:
                handle_drop("Connection closed by server")
                continue

            message = data.decode("utf-8")
            print(f"\nfrom {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
            print("> ", end="", flush=True)

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            handle_drop("Connection lost")

        except Exception as e:
            handle_drop(f"Error receiving: {e}")
            await asyncio.sleep(1)


def handle_drop(reason):
    """Mark the connection as dead and let the connection handler reconnect."""
    connected, _, _, _ = get_connection_state()

    # the disconnect command already cleared the flag, so this drop was intentional
    if not connected:
        return

    set_connected(False)
    set_auto_reconnect(True)
    print(f"\n{reason}")
    print("> ", end="", flush=True)
