from shared.colors import RED, RESET
from shared.symbols import ERROR, QUESTION
from shared.config import get_config

command = ["shutdown","exit","quit"]
description = "Shuts down the application"

def function():
    print(f"{QUESTION} Are you sure you want to shut down the application? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        print(f"{RED}{get_config('NAME')}#{get_config('ID')}{RESET} is shutting down.")
        exit(0)
    else:
        print(f"{ERROR} Operation cancelled.")
