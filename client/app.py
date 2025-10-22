import os
import asyncio

from utils.config import get_config
from handlers.connection_handler import connect_to_server_async
from handlers.command_handler import command_handler_async
from handlers.message_handler import receive_messages_async

NAME = get_config("NAME")
ID = get_config("ID")
VERSION = get_config("VERSION")

# init app
os.system("color")
os.system(f"title {NAME}#{ID} {VERSION}")

# global vars
CONNECTED = False
reader = None
writer = None
server_info = {}

# run handlers in parallel
async def main():
    global CONNECTED, reader, writer, server_info
    
    # handlers
    await asyncio.gather(
        connect_to_server_async(),
        receive_messages_async(),
        command_handler_async()
    )

# main
if __name__ == "__main__":
    try:
        try:
            import uvloop # type: ignore
            uvloop.install()
            print("Using uvloop asyncio")
        except ImportError:
            print("Using standard asyncio")
        asyncio.run(main())
    
    except KeyboardInterrupt:
        print(f"\n{NAME} is shutting down.")
    except Exception as e:
        print(f"Fatal error: {e}")