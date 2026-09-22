import os

from shared.symbols import SUCCESS, ERROR, QUESTION
from handlers.client_handler import get_clients_file

command = ["data clients clear","data clients cls"]
description = "Clears the client list"

async def function():
    print(f"{QUESTION} Are you sure you want to clear the client list? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        clients_file = get_clients_file()
        if os.path.exists(clients_file):
            os.remove(clients_file)
            print(f"{SUCCESS} List of clients has been cleared.")
        else:
            print(f"{ERROR} List of clients not found.")
    else:
        print(f"{ERROR} Operation cancelled.")
