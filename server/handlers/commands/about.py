import re

from utils.colors import GREEN, RED, GRAY, RESET
from utils.config import get_config
from utils.network import get_connection

command = ["about", "self", "info"]
description = "Information about the application"

gap = 50
margin = " " * 5

async def function():
    # read at call time, the config changes while the server runs
    name = get_config("NAME")
    server_id = get_config("ID")
    server_type = get_config("TYPE")
    version = get_config("VERSION")
    host = get_config("HOST")
    port = get_config("PORT")

    status = f"{GREEN}True{RESET}" if get_connection() else f"{RED}False{RESET}"
    plain_status = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', status)

    print("\n" + margin + f"{name}#{server_id}")
    print(margin + f"{GRAY}{'─' * gap}{RESET}")
    print(margin + f"{'Name:'.ljust(gap-len(name))}{name}")
    print(margin + f"{'ID:'.ljust(gap-len(server_id))}{server_id}")
    print(margin + f"{'Type:'.ljust(gap-len(server_type))}{server_type}")
    print(margin + f"{'Version:'.ljust(gap-len(version))}{version}")
    print(margin + f"{'Host/Address:'.ljust(gap-len(host))}{host}")
    print(margin + f"{'Port:'.ljust(gap-len(str(port)))}{port}")
    print(margin + f"{'Connected:'.ljust(gap-len(plain_status))}{status}\n")
