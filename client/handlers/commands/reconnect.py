from handlers.connection_handler import set_connected, set_auto_reconnect, get_connection_state

command = ["reconnect", "rc"]
description = "Reconnect to server"


async def function():
    _, _, writer, _ = get_connection_state()
    
    set_connected(False)
    set_auto_reconnect(True)
    
    if writer:
        writer.close()
        await writer.wait_closed()
    
    print("Attempting to reconnect...")