from shared.console import ask
from shared.symbols import SUCCESS, ERROR, QUESTION
from handlers import store
from handlers.client_handler import get_connected_clients

command = ["data clients clear","data clients cls"]
description = "Clears the client list, with their state and history"

async def function():
    print(f"{QUESTION} Are you sure you want to clear the client list, their state and history? (y/n)")
    # the server keeps answering clients and the dashboard while this waits
    answer = await ask(">")
    if answer.strip().lower() == "y":
        count = store.clear_clients()
        # a client still connected must stay known: its next state needs its row,
        # the history refers to it; this is what its handshake did
        connected = list(get_connected_clients().values())
        for info in connected:
            store.upsert_client(info["id"], info["name"], info["device"], info["capabilities"])
        if count:
            kept = f", {len(connected)} connected kept" if connected else ""
            print(f"{SUCCESS} List of clients has been cleared{kept}.")
        else:
            print(f"{ERROR} List of clients is already empty.")
    else:
        print(f"{ERROR} Operation cancelled.")
