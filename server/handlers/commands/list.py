import json
import os

from shared.colors import GREEN, GRAY, RESET
from handlers.client_handler import get_connected_clients, get_clients_file

command = ["list", "ls"]
description = "List all clients"

async def function():
    clients_file = get_clients_file()
    print("\n" + " " * 5 + "List of clients:")
    print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")

    if not os.path.exists(clients_file):
        print(" " * 5 + "No clients found\n")
        return

    with open(clients_file, "r", encoding="utf-8") as f:
        try:
            clients = json.load(f)
        except json.JSONDecodeError:
            print(" " * 5 + "Error loading clients\n")
            return

    if not clients:
        print(" " * 5 + "No clients found\n")
        return

    # Get online clients
    connected_clients = get_connected_clients()

    # id -> (address, device) of the client that is currently connected under that id
    online = {}
    for addr, client_data in connected_clients.items():
        online[client_data.get("id")] = (f"{addr[0]}:{addr[1]}", client_data.get("device"))

    # Display clients
    for i, client in enumerate(clients, 1):
        client_id = client.get("ID", "?")
        client_name = client.get("NAME", "Unknown")

        if client_id in online:
            address, device = online[client_id]
            device_text = f" {device}" if device else ""
            print(" " * 5 + f"#{i} {GREEN}{client_name}#{client_id} ({address}){RESET}{device_text}")
        else:
            print(" " * 5 + f"#{i} {GRAY}{client_name}#{client_id}{RESET}")
    print()
