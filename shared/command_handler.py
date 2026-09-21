"""Loads command modules and runs the console prompt.

A command is a module that declares three things:

    command = ["mycommand", "mc"]     first name is canonical, rest are aliases
    description = "What it does"
    async def function(*params):      may also be a plain def

Commands are loaded from several folders. Later folders win, so a side can
replace a shared command with its own version of it.
"""
import importlib
import inspect
import os
import asyncio

from shared.console import PROMPT
from shared.symbols import ERROR

_commands = {}


def get_commands():
    """The commands loaded at startup, keyed by name and by alias."""
    return _commands


def load_commands(sources):
    """sources is a list of (directory, package name) pairs."""
    _commands.clear()

    for directory, package in sources:
        if not os.path.isdir(directory):
            continue

        for file in sorted(os.listdir(directory)):
            if not file.endswith(".py") or file == "__init__.py":
                continue

            module_name = file[:-3]

            try:
                module = importlib.import_module(f"{package}.{module_name}")

                names = getattr(module, "command", [])
                if isinstance(names, str):
                    names = [names]
                if not names:
                    continue

                run_func = getattr(module, "function", None)
                if not callable(run_func):
                    continue

                description = getattr(module, "description", "blank")

                for name in names:
                    _commands[name.lower()] = {
                        "name": names[0].lower(),
                        "aliases": names[1:],
                        "description": description,
                        "run": run_func,
                    }

            except Exception as e:
                print(f"{ERROR} Failed to load command '{module_name}': {e}")

    return _commands


def match_command(commands, cmd_input):
    """Some commands are several words long, so match the longest name first."""
    lowered = cmd_input.lower()
    for name in sorted(commands, key=len, reverse=True):
        if lowered == name:
            return name, []
        if lowered.startswith(name + " "):
            return name, cmd_input[len(name):].split()
    return None, []


async def command_handler_async(sources):
    commands = load_commands(sources)
    loop = asyncio.get_event_loop()

    while True:
        try:
            # input blocks, so it runs off the event loop
            cmd_input = await loop.run_in_executor(None, input, PROMPT)
            cmd_input = cmd_input.strip()

            if not cmd_input:
                continue

            cmd, params = match_command(commands, cmd_input)

            if not cmd:
                print(f"{ERROR} Unknown command. Type 'help' for list of commands.")
                continue

            try:
                run = commands[cmd]["run"]
                if inspect.iscoroutinefunction(run):
                    await run(*params)
                else:
                    await loop.run_in_executor(None, run, *params)
            except TypeError as e:
                # most likely the command was given parameters it does not take
                print(f"{ERROR} Bad parameters for '{cmd}': {e}")
            except Exception as e:
                print(f"{ERROR} Error running command '{cmd}': {e}")

        except EOFError:
            # stdin closed, nothing left to read
            return
        except Exception as e:
            print(f"{ERROR} Command handler error: {e}")
