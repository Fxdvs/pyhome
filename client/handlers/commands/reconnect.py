from handlers.connection_handler import connection

command = ["reconnect", "rc"]
description = "Reconnect to server"


async def function():
    writer = connection.detach()
    connection.auto_reconnect = True

    if writer:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    print("Attempting to reconnect...")
