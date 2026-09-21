from shared.colors import GREEN, RED, RESET
from shared.config import get_config
from shared.console import print_info
from shared.network import get_connection

command = ["about", "self", "info"]
description = "Information about the application"


async def function():
    # read at call time, the config changes while the server runs
    name = get_config("NAME")
    server_id = get_config("ID")
    status = f"{GREEN}True{RESET}" if get_connection() else f"{RED}False{RESET}"

    print_info(f"{name}#{server_id}", [
        ("Name:", name),
        ("ID:", server_id),
        ("Type:", get_config("TYPE")),
        ("Version:", get_config("VERSION")),
        ("Host/Address:", get_config("HOST")),
        ("Port:", get_config("PORT")),
        ("Connected:", status),
    ])
