from utils.colors import RED, RESET
from utils.symbols import ERROR, QUESTION
from utils.config import get_config

command = ["shutdown","exit","quit"]
description = "Shuts down the server"

NAME = get_config("NAME")
ID = get_config("ID")

def close():
    print(f"{QUESTION} Are you sure you want to shut down the server? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        print(f"{RED}{NAME}#{ID}{RESET} is shutting down.")
        exit(0)      
    else:
        print(f"{ERROR} Operation cancelled.")

