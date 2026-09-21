import re

from utils.colors import GREEN, RED, GRAY, RESET
from utils.config import get_config
from handlers.connection_handler import get_connection_state


command = ["about", "self", "info"]
description = "Information about the application"

gap = 50
margin = " " * 5

async def function():
    # read at call time, the config changes while the client runs
    name = get_config("NAME")
    client_id = get_config("ID")
    client_type = get_config("TYPE")
    version = get_config("VERSION")
    host = get_config("HOST")
    port = get_config("PORT")

    status = f"{GREEN}True{RESET}" if get_connection_state()[0] else f"{RED}False{RESET}"
    plain_status = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', status)

    print("\n" + margin + f"{name}#{client_id}")
    print(margin + f"{GRAY}{'─' * gap}{RESET}")
    print(margin + f"{'Name:'.ljust(gap-len(name))}{name}")
    print(margin + f"{'ID:'.ljust(gap-len(client_id))}{client_id}")
    print(margin + f"{'Type:'.ljust(gap-len(client_type))}{client_type}")
    print(margin + f"{'Version:'.ljust(gap-len(version))}{version}")
    print(margin + f"{'Host/Address:'.ljust(gap-len(host))}{host}")
    print(margin + f"{'Port:'.ljust(gap-len(str(port)))}{port}")
    print(margin + f"{'Connected:'.ljust(gap-len(plain_status))}{status}\n")
