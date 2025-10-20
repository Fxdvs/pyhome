import os
import asyncio

from utils.config import get_config
from handlers.server_handler import start_server_async
from handlers.command_handler import command_handler_async
from handlers.client_handler import handle_client_async

NAME = get_config("NAME")
ID = get_config("ID")
VERSION = get_config("VERSION")

# init app
os.system("color")
os.system(f"title {NAME}#{ID} {VERSION}")

# handle client connections
async def accept_clients(server):
    async with server:
        await server.serve_forever()

# run handlers in parallel
async def main():
    server = await start_server_async()
    
    # handlers
    await asyncio.gather(
        accept_clients(server),
        command_handler_async()
    )

# main
if __name__ == "__main__":
    try:
         # try to use uvloop if os supports it
        try:
            import uvloop # type: ignore
            uvloop.install()
            print("Using uvloop asyncio")
        except ImportError:
            print("Using standard asyncio")
        asyncio.run(main())
    
    except KeyboardInterrupt:
        print(f"\n{NAME} is turned off.")
    except Exception as e:
        print(f"Fatal error: {e}")