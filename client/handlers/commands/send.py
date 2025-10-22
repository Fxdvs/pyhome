from utils.colors import GREEN, RESET
from handlers.connection_handler import get_connection_state, get_connection_lock

command = ["send", "msg"]
description = "Send message to server"


async def function(*params):
    """Send message to server"""
    CONNECTED, reader, writer, server_info = get_connection_state()
    connection_lock = get_connection_lock()
    
    if not CONNECTED:
        print("Not connected to server")
        return
    
    print("\n" + " " * 5 + "Connected server")
    print(" " * 5 + f"{GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}\n")
    
    # Get message (can also use params if passed)
    if params:
        message = " ".join(params)
    else:
        import asyncio
        loop = asyncio.get_event_loop()
        message = await loop.run_in_executor(None, input, "> (message) ")
        message = message.strip()
    
    if message:
        print(f"> sent {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
        
        async with connection_lock:
            if CONNECTED and writer:
                try:
                    writer.write(message.encode('utf-8'))
                    await writer.drain()
                except Exception as e:
                    print(f"Error sending message: {e}")
    else:
        print("No message sent")