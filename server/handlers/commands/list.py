import json
import os

from utils.colors import GREEN, GRAY, RESET
from handlers.client_handler import get_connected_clients

command = ["list", "ls"]
description = "List all clients"

CLIENTS_FILE = "data/clients.json"

async def function():
    print("\n" + " " * 5 + "List of clients:")
    print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
    
    if not os.path.exists(CLIENTS_FILE):
        print(" " * 5 + "No clients found\n")
        return
    
    with open(CLIENTS_FILE, "r") as f:
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
    
    online_ids = set()
    for addr, client_data in connected_clients.items():
        online_ids.add(client_data.get("id"))
    
    # Display clients
    for i, client in enumerate(clients, 1):
        client_id = client.get("ID", "?")
        client_name = client.get("NAME", "Unknown")
        
        is_online = client_id in online_ids
        if is_online:
            ip, port = addr
            print(" " * 5 + f"#{i} {GREEN}{client_name}#{client_id} ({ip}:{port}){RESET}")
        else:
            print(" " * 5 + f"#{i} {GRAY}{client_name}#{client_id}{RESET}")
    print()