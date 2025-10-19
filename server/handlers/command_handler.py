import importlib
import os
from utils.symbols import ERROR

COMMANDS_PATH = os.path.join(os.path.dirname(__file__), "commands")

# load commands
def load_commands():
    commands = {}
    for file in os.listdir(COMMANDS_PATH):
        if not file.endswith(".py") or file == "__init__.py":
            continue
        command_name = file[:-3]
        command_path = f"handlers.commands.{command_name}"
        try:
            # load command
            command = importlib.import_module(command_path)
            names = getattr(command, "command", [])
            if isinstance(names, str):
                names = [names]
            description = getattr(command, "description", "blank")

            # find func
            run_func = None
            for attr_name in dir(command):
                attr = getattr(command, attr_name)
                if callable(attr) and not attr_name.startswith("_"):
                    run_func = attr
                    break
            
            if run_func:
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

def command_handler():
    commands = load_commands() 
    while True:
        cmd = input("> ").strip().lower()
        if cmd in commands:
            try:
                commands[cmd]["run"]()
            except Exception as e:
                print(f"{ERROR} Error running command '{cmd}': {e}")
            continue
        if cmd == "":
            continue
        print(f"{ERROR} Unknown command. Type 'help' for list of commands.")


        
