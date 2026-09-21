from shared.config import get_config
from shared.console import print_info

command = ["data config show","data conf show"]
description = "Shows formatted config.json"


async def function():
    # read at call time, the config changes while the server runs
    print_info("/data/config.json", [
        ("Name:", get_config("NAME")),
        ("ID:", get_config("ID")),
        ("Type:", get_config("TYPE")),
        ("Version:", get_config("VERSION")),
        ("Host/Address:", get_config("HOST")),
        ("Port:", get_config("PORT")),
    ])
