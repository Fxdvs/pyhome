import asyncio

from utils.colors import GREEN, RESET
from utils.config import get_config
from handlers.client_handler import handle_client_async

NAME = get_config("NAME")
ID = get_config("ID")
HOST = get_config("HOST")
PORT = get_config("PORT")

async def start_server_async():
    server = await asyncio.start_server(
        handle_client_async,
        HOST,
        PORT
    )

    addr = server.sockets[0].getsockname()
    print(f"{GREEN}{NAME}#{ID}{RESET} running on {addr[0]}:{addr[1]}")
    
    return server