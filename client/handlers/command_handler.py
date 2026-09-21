import importlib
import inspect
import os
import asyncio

from utils.symbols import ERROR

COMMANDS_PATH = os.path.join(os.path.dirname(__file__), "commands")

def load_commands():
    commands = {}
    for file in os.listdir(COMMANDS_PATH):
        if not file.endswith(".py") or file == "__init__.py":
            continue
        command_name = file[:-3]
        command_path = f"handlers.commands.{command_name}"

        try:
            command = importlib.import_module(command_path)
            names = getattr(command, "command", [])

            if isinstance(names, str):
                names = [names]
            description = getattr(command, "description", "blank")

            run_func = getattr(command, "function", None)

            if callable(run_func):
                for name in names:
                    commands[name.lower()] = {
                        "name": names[0].lower(),
                        "aliases": names[1:],
                        "description": description,
                        "run": run_func
                    }
        except Exception as e:
            print(f"{ERROR} Failed to load command '{command_name}': {e}")
    return commands

def match_command(commands, cmd_input):
    """Some commands are several words long, so match the longest name first."""
    lowered = cmd_input.lower()
    for name in sorted(commands, key=len, reverse=True):
        if lowered == name:
            return name, []
        if lowered.startswith(name + " "):
            return name, cmd_input[len(name):].split()
    return None, []

async def command_handler_async():
    commands = load_commands()
    loop = asyncio.get_event_loop()

    while True:
        try:
            # Read input without blocking
            cmd_input = await loop.run_in_executor(None, input, "> ")
            cmd_input = cmd_input.strip()

            if not cmd_input:
                continue

            cmd, params = match_command(commands, cmd_input)

            if cmd:
                try:
                    # Check if command is async
                    if inspect.iscoroutinefunction(commands[cmd]["run"]):
                        await commands[cmd]["run"](*params)
                    else:
                        await loop.run_in_executor(None, commands[cmd]["run"], *params)
                except Exception as e:
                    print(f"{ERROR} Error running command '{cmd}': {e}")
            else:
                print(f"{ERROR} Unknown command. Type 'help' for list of commands.")

        except Exception as e:
            print(f"{ERROR} Command handler error: {e}")
