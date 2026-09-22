from shared.config import load_config
from handlers.connection_handler import connection

command = ["reconnect", "rc"]
description = "Reconnect to server, re-reading the config first"


async def function():
    # a corrected TOKEN or address takes effect without restarting the client
    load_config(reload=True)

    writer = connection.detach()
    connection.auto_reconnect = True

    if writer:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    print("Attempting to reconnect...")
