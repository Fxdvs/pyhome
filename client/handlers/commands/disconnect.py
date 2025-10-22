from handlers.connection_handler import set_connected, set_auto_reconnect, get_connection_state

command = ["disconnect", "dc"]
description = "Disconnect from server"


async def function():
    _, _, writer, _ = get_connection_state()
    
    set_connected(False)
    set_auto_reconnect(False)
    
    if writer:
        writer.close()
        await writer.wait_closed()
    
    print("Disconnected from server.")