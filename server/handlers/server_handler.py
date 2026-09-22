import asyncio

from shared.colors import GREEN, RESET, YELLOW
from shared.config import get_config
from shared.symbols import WARNING
from handlers.client_handler import handle_client_async, token_warning

async def start_server_async():
    server = await asyncio.start_server(
        handle_client_async,
        get_config("HOST"),
        get_config("PORT")
    )

    addr = server.sockets[0].getsockname()
    print(f"{GREEN}{get_config('NAME')}#{get_config('ID')}{RESET} running on {addr[0]}:{addr[1]}")

    # an open door should be visible, not silent
    warning = token_warning()
    if warning:
        print(f"{WARNING} {YELLOW}{warning}{RESET}")

    return server
