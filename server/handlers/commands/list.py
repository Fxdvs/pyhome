from shared.colors import GREEN, GRAY, RESET
from handlers import store
from handlers.client_handler import get_connected_clients

command = ["list", "ls"]
description = "List all clients"

async def function():
    print("\n" + " " * 5 + "List of clients:")
    print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")

    clients = store.list_clients()
    if not clients:
        print(" " * 5 + "No clients found\n")
        return

    # id -> (address, device) of the client that is currently connected under that id
    online = {}
    for addr, client_data in get_connected_clients().items():
        online[str(client_data.get("id"))] = (f"{addr[0]}:{addr[1]}", client_data.get("device"))

    for i, client in enumerate(clients, 1):
        client_id = client["id"]
        client_name = client["name"]

        if client_id in online:
            address, device = online[client_id]
            device_text = f" {device}" if device else ""
            print(" " * 5 + f"#{i} {GREEN}{client_name}#{client_id} ({address}){RESET}{device_text}")
        else:
            print(" " * 5 + f"#{i} {GRAY}{client_name}#{client_id}{RESET}")
    print()
