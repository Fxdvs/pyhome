import importlib
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
            
            # Find run function
            run_func = None
            for attr_name in dir(command):
                attr = getattr(command, "function", None)
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
            
            # Parse command and parameters
            parts = cmd_input.split()
            cmd = parts[0].lower()
            params = parts[1:] if len(parts) > 1 else []
            
            if cmd in commands:
                try:
                    # Check if command is async
                    import inspect
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