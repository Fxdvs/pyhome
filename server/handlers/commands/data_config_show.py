from utils.colors import GRAY, RESET
from utils.config import get_config

command = ["data config show","data conf show"]
description = "Shows formatted config.json"

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

    print("\n" + margin + "/data/config.json")
    print(margin + f"{GRAY}{'─' * gap}{RESET} ")
    print(margin + f"{'Name:'.ljust(gap-len(name))}{name}")
    print(margin + f"{'ID:'.ljust(gap-len(server_id))}{server_id}")
    print(margin + f"{'Type:'.ljust(gap-len(server_type))}{server_type}")
    print(margin + f"{'Version:'.ljust(gap-len(version))}{version}")
    print(margin + f"{'Host/Adress:'.ljust(gap-len(host))}{host}")
    print(margin + f"{'Port:'.ljust(gap-len(str(port)))}{port}")
    print("")
