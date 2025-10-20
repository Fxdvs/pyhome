import os

from utils.symbols import SUCCESS, ERROR, QUESTION

command = ["data clients clear","data clients cls"]
description = "Clears the client list"

async def data_clients_clear():   
    print(f"{QUESTION} Are you sure you want to clear the client list? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        if os.path.exists("/data/clients.json"):
            os.remove("/data/clients.json")
            print(f"{SUCCESS} List of clients has been cleared.")
        else:
            print(f"{ERROR} List of clients not found.")
    else:
        print(f"{ERROR} Operation cancelled.")
