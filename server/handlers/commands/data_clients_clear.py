import os

from utils.symbols import SUCCESS, ERROR, QUESTION
from handlers.client_handler import CLIENTS_FILE

command = ["data clients clear","data clients cls"]
description = "Clears the client list"

async def function():
    print(f"{QUESTION} Are you sure you want to clear the client list? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        if os.path.exists(CLIENTS_FILE):
            os.remove(CLIENTS_FILE)
            print(f"{SUCCESS} List of clients has been cleared.")
        else:
            print(f"{ERROR} List of clients not found.")
    else:
        print(f"{ERROR} Operation cancelled.")
