import os

from shared.colors import GRAY, RESET
from shared.symbols import SUCCESS, ERROR, QUESTION
from shared.config import get_config, set_config

command = ["data config edit name","data conf edit name"]
description = "Edits the server name"

gap = 50
margin = " " * 5

async def function():
    # read at call time, the name changes while the server runs
    name = get_config("NAME")

    print(f"{QUESTION} Are you sure you want to edit the server name? (y/n)")
    accept = input(">").strip().lower()
    if accept != "y":
        print(f"{ERROR} Operation cancelled.")
        return

    print("\n" + margin + "/data/config.json")
    print(margin + f"{GRAY}{'─' * gap}{RESET}")
    print(margin + f"{'From:'.ljust(gap-len(name))}{name}\n")

    new_name = input("> ").strip()
    if new_name != "":
        print("\n" + margin + "/data/config.json")
        print(margin + f"{GRAY}{'─' * gap}{RESET}")
        print(margin + f"{'From:'.ljust(gap-len(name))}{name}")
        print(margin + f"{'To:'.ljust(gap-len(new_name))}{new_name}\n")

        print(f"{QUESTION} Are you sure you want to edit the server name to '{new_name}'? (y/n)")
        accept = input("> ").strip().lower()
        if accept == "y":
            set_config("NAME", new_name)
            print(f"{SUCCESS} Name has been changed to '{new_name}'!")
            if os.name == "nt":
                try:
                    os.system(f"title {new_name}#{get_config('ID')} {get_config('VERSION')}")
                except Exception as e:
                    print(f"{ERROR} Error setting title: {e}")
        else:
           print(f"{ERROR} Operation cancelled.")
    else:
        print(f"{ERROR} Operation cancelled, name cannot be empty.")
