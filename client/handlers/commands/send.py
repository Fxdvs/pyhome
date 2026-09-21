import asyncio

from shared.colors import GREEN, RESET
from shared.protocol import MESSAGE, send_message
from handlers.connection_handler import connection

command = ["send", "msg"]
description = "Send message to server"


async def function(*params):
    if not connection.connected:
        print("Not connected to server")
        return

    print("\n" + " " * 5 + "Connected server")
    print(" " * 5 + f"{GREEN}{connection.label}{RESET}\n")

    # the message can come as parameters, otherwise ask for it
    if params:
        message = " ".join(params)
    else:
        loop = asyncio.get_event_loop()
        message = await loop.run_in_executor(None, input, "> (message) ")
        message = message.strip()

    if not message:
        print("No message sent")
        return

    async with connection.lock:
        if not connection.connected or not connection.writer:
            print("Not connected to server")
            return
        try:
            await send_message(connection.writer, MESSAGE, text=message)
            print(f"> sent {GREEN}{connection.label}{RESET} {message}")
        except Exception as e:
            print(f"Error sending message: {e}")
