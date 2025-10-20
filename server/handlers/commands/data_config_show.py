from utils.colors import GRAY, RESET
from utils.config import get_config

command = ["data config show","data conf show"]
description = "Shows formatted config.json"

NAME = get_config("NAME")
ID = get_config("ID")
TYPE = get_config("TYPE")
VERSION = get_config("VERSION")
HOST = get_config("HOST")
PORT = get_config("PORT")

gap = 50
margin = " " * 5

async def data_config_show():
    print("\n" + margin + "/data/config.json")
    print(margin + f"{GRAY}{'─' * gap}{RESET} ")
    print(margin + f"{'Name:'.ljust(gap-len(NAME))}{NAME}")
    print(margin + f"{'ID:'.ljust(gap-len(ID))}{ID}")
    print(margin + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
    print(margin + f"{'Version:'.ljust(gap-len(VERSION))}{VERSION}")
    print(margin + f"{'Host/Adress:'.ljust(gap-len(HOST))}{HOST}")
    print(margin + f"{'Port:'.ljust(gap-len(str(PORT)))}{PORT}")
    print("")