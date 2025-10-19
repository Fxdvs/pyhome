import os
from time import sleep

command = "restart"
description = "Restarts the server"

from utils.colors import GRAY, RESET, RED
from utils.symbols import SUCCESS, ERROR, QUESTION

def restart():
    print(f"{QUESTION} Are you sure you want to restart the server? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        os.system("cls")
        print("\n" + " " * 5 + "Server restarting...")
        print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
        for i in range(1,6):
            print(" " * 5 + f"Restarting in {RED}{i}{RESET} seconds")
            sleep(1)
        os.system("cls")
    else:
        print(f"{ERROR} Operation cancelled.")
