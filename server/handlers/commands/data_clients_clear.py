from shared.symbols import SUCCESS, ERROR, QUESTION
from handlers import store

command = ["data clients clear","data clients cls"]
description = "Clears the client list"

async def function():
    print(f"{QUESTION} Are you sure you want to clear the client list? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        # their state and history go with them
        count = store.clear_clients()
        if count:
            print(f"{SUCCESS} List of clients has been cleared.")
        else:
            print(f"{ERROR} List of clients is already empty.")
    else:
        print(f"{ERROR} Operation cancelled.")
