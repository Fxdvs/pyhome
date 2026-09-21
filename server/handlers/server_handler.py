import asyncio

from shared.colors import GREEN, RESET
from shared.config import get_config
from handlers.client_handler import handle_client_async

async def start_server_async():
    server = await asyncio.start_server(
        handle_client_async,
        get_config("HOST"),
        get_config("PORT")
    )

    addr = server.sockets[0].getsockname()
    print(f"{GREEN}{get_config('NAME')}#{get_config('ID')}{RESET} running on {addr[0]}:{addr[1]}")

    return server
