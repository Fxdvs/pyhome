from shared.colors import GREEN, RED, RESET
from shared.config import get_config
from shared.console import print_info
from client_handlers.connection_handler import connection
from client_handlers.device_handler import get_capabilities

command = ["about", "self", "info"]
description = "Information about the application"


async def function():
    # read at call time, the config changes while the client runs
    name = get_config("NAME")
    client_id = get_config("ID")
    status = f"{GREEN}True{RESET}" if connection.connected else f"{RED}False{RESET}"

    print_info(f"{name}#{client_id}", [
        ("Name:", name),
        ("ID:", client_id),
        ("Type:", get_config("TYPE")),
        ("Device:", get_config("DEVICE") or "none"),
        ("Capabilities:", ", ".join(get_capabilities()) or "none"),
        ("Version:", get_config("VERSION")),
        ("Host/Address:", get_config("HOST")),
        ("Port:", get_config("PORT")),
        ("Token:", "set" if get_config("TOKEN") else "not set"),
        ("TLS:", "on" if connection.tls else ("set, not connected" if get_config("TLS_CA") else f"{RED}off{RESET}")),
        ("Connected:", status),
    ])
