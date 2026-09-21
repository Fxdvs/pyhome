import os
import asyncio
import uvicorn

from utils.config import get_config
from handlers.server_handler import start_server_async
from handlers.command_handler import command_handler_async
from handlers.client_handler import handle_client_async
from handlers.web_handler import app

NAME = get_config("NAME")
ID = get_config("ID")
VERSION = get_config("VERSION")

# init app, both commands only exist on windows
if os.name == "nt":
    os.system("color")
    os.system(f"title {NAME}#{ID} {VERSION}")

# handle client connections
async def accept_clients(server):
    async with server:
        await server.serve_forever()
        
async def start_web():
    config = uvicorn.Config(app, host="0.0.0.0", port=50001, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# run handlers in parallel
async def main():
    server = await start_server_async()
    
    # handlers
    await asyncio.gather(
        accept_clients(server),
        start_web(),
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