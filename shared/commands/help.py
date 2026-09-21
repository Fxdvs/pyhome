from shared.colors import GRAY, RESET
from shared.command_handler import get_commands

command = ["help", "commands", "?"]
description = "Lists all available commands and their descriptions."

gap = 35
margin = " " * 5


def function():
    # the registry is keyed by name and by alias, so collapse it back down
    commands = {}
    for entry in get_commands().values():
        commands[entry["name"]] = entry

    print("\n" + margin + f"{'Command'.ljust(gap)}{'Aliases'.ljust(gap)}Description")
    print(margin + f"{GRAY}{'─' * (gap * 3 + 30)}{RESET}")

    for name in sorted(commands):
        entry = commands[name]
        aliases = ", ".join(entry["aliases"]) if entry["aliases"] else "-"
        print(
            margin
            + f"{name.ljust(gap)}"
            + f"{aliases.ljust(gap)}"
            + f"{entry['description']}"
        )
    print()
