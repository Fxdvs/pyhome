from handlers.connection_handler import connection

command = ["disconnect", "dc"]
description = "Disconnect from server"


async def function():
    if not connection.connected:
        print("Not connected to server")
        return

    # clear the flag first, so the receive loop treats the drop as intentional
    connection.auto_reconnect = False
    writer = connection.detach()

    if writer:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    print("Disconnected from server.")
