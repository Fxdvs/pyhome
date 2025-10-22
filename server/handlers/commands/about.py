import re

from utils.colors import GREEN, RED, GRAY, RESET
from utils.config import get_config
from utils.network import get_connection

command = ["about", "self", "info"]
description = "Information about the application"

NAME = get_config("NAME")
ID = get_config("ID")
TYPE = get_config("TYPE")
VERSION = get_config("VERSION")
HOST = get_config("HOST")
PORT = get_config("PORT")

gap = 50
margin = " " * 5
name = f"{NAME}#{ID}"

async def function():
    status = f"{GREEN}True{RESET}" if get_connection() else f"{RED}False{RESET}"
    
    print("\n" + margin + f"{name}")
    print(margin + f"{GRAY}{'─' * gap}{RESET}")
    print(margin + f"{'Name:'.ljust(gap-len(NAME))}{NAME}")
    print(margin + f"{'ID:'.ljust(gap-len(ID))}{ID}")
    print(margin + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
    print(margin + f"{'Version:'.ljust(gap-len(VERSION))}{VERSION}")
    print(margin + f"{'Host/Address:'.ljust(gap-len(HOST))}{HOST}")
    print(margin + f"{'Port:'.ljust(gap-len(str(PORT)))}{PORT}")
    print(margin + f"{'Connected:'.ljust(gap-len(re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', status)))}{status}\n")
    