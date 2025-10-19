import os
import json
from utils.colors import GREEN, GRAY, RESET
from handlers.client_handler import connected_clients, clients_lock

command = ["list", "ls"]
description = "Lists all clients"

CLIENTS_FILE = "data/clients.json"

margin = " " * 5

def list_clients():
    print("\n" + margin + "List of connected clients")
    print(margin + f"{GRAY}{'─' * 50}{RESET}")

    if not os.path.exists(CLIENTS_FILE):
        print(margin + "No clients found\n")
        return
    
    try:
        with open(CLIENTS_FILE, "r") as f:
            clients_data = json.load(f)
    except Exception:
        print(margin + "Failed to read clients file\n")
        return
    
    if not clients_data:
        print(margin + "No clients found\n")
        return
    
    for idx, client in enumerate(clients_data, 1):
        client_name = client.get("NAME", "Unknown")
        client_id_val = client.get("ID", "Unknown")
        client_key = f"{client_name}#{client_id_val}"

        is_online = False
        with clients_lock:
            for addr, client_data in connected_clients.items():
                if isinstance(client_data, dict):
                    online_key = f"{client_data.get('name', '')}#{client_data.get('id', '')}"
                    if online_key == client_key:
                        is_online = True
                        break
        color = GREEN if is_online else GRAY
        print(f"{margin}#{idx} {color}{client_key}{RESET}")
    print()
