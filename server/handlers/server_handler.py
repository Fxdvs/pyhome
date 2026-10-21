import asyncio
import sys

from shared.colors import GREEN, RESET, YELLOW
from shared.config import get_config
from shared.network import is_address_in_use, port_in_use_message
from shared.symbols import ERROR, WARNING
from handlers.client_handler import handle_client_async, token_warning
from handlers.tls import TLSConfigError, server_context, startup_lines

async def start_server_async():
    # a typo in TLS_CERT must stop the server, running unencrypted would look like it works
    try:
        context = server_context()
    except TLSConfigError as e:
        sys.exit(f"{ERROR} {e}")

    try:
        server = await asyncio.start_server(
            handle_client_async,
            get_config("HOST"),
            get_config("PORT"),
            ssl=context,
        )
    except OSError as e:
        if is_address_in_use(e):
            sys.exit(f"{ERROR} {port_in_use_message(get_config('PORT'), 'clients')}")
        raise

    addr = server.sockets[0].getsockname()
    print(f"{GREEN}{get_config('NAME')}#{get_config('ID')}{RESET} running on {addr[0]}:{addr[1]}")

    for is_warning, text in startup_lines():
        print(f"{WARNING} {YELLOW}{text}{RESET}" if is_warning else text)

    # an open door should be visible, not silent
    warning = token_warning()
    if warning:
        print(f"{WARNING} {YELLOW}{warning}{RESET}")

    return server
