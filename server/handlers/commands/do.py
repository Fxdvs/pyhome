from shared.colors import GRAY, RESET
from shared.symbols import ERROR
from handlers.client_handler import get_connected_clients
from handlers.devices import parse_params, run_and_print

command = ["do"]
description = "Runs a device action on a client: do <id> <action> [key=value ...]"


async def function(*params):
    if len(params) < 2:
        print(f"{ERROR} Usage: do <client id> <action> [key=value ...]")
        online = [f"{info['id']} ({info.get('device') or 'no device'})"
                  for info in get_connected_clients().values()]
        if online:
            print(f"{GRAY}      online: {', '.join(sorted(online))}{RESET}")
        else:
            print(f"{GRAY}      no clients are connected{RESET}")
        return

    try:
        values = parse_params(params[2:])
    except ValueError as e:
        print(f"{ERROR} {e}")
        return

    await run_and_print(params[0], params[1], values)
