import importlib
import os

from utils.colors import GRAY, RESET
from utils.symbols import ERROR

command = ["help", "commands", "?"]
description = "Lists all available commands and their descriptions."

COMMANDS_PATH = os.path.join(os.path.dirname(__file__), "..", "commands")

gap = 35
margin = " " * 5

def help():
    commands = []
    for file in os.listdir(COMMANDS_PATH):
        if not file.endswith(".py") or file == "__init__.py":
            continue

        command_name = file[:-3]
        command_path = f"handlers.commands.{command_name}"

        try:
            module = importlib.import_module(command_path)

            names = getattr(module, "command", [])
            if isinstance(names, str):
                names = [names]

            description = getattr(module, "description", "blank")

            commands.append({
                "name": names[0].lower(),
                "aliases": names[1:],
                "description": description,
            })
        except Exception as e:
            print(f"{ERROR} Failed to load command '{file}': {e}")

    # sort by name
    commands.sort(key=lambda x: x["name"])

    print("\n" + margin + f"{'Command'.ljust(gap)}{'Aliases'.ljust(gap)}Description")
    print(margin + f"{GRAY}{'─' * (gap * 3 + 30)}{RESET}")
    shown = set()
    for cmd in commands:
        if cmd["name"] not in shown:
            aliases = ", ".join(cmd["aliases"]) if cmd["aliases"] else "-"
            print(
                margin
                + f"{cmd['name'].ljust(gap)}"
                + f"{aliases.ljust(gap)}"
                + f"{cmd['description']}"
            )
            shown.add(cmd["name"])
    print()
