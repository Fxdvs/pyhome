import json
import os
from utils.colors import GREEN, GRAY, RESET
from handlers.client_handler import get_connected_clients, get_clients_lock

command = ["list", "ls"]
description = "List all clients (use -b for grid view)"

CLIENTS_FILE = "data/clients.json"


def list_clients(*params):
    """List clients - supports -b parameter for grid view"""
    
    # Check for -b parameter
    if "-b" in params or "--big" in params:
        list_big()
    else:
        list_normal()


def list_normal():
    """Normal list view"""
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
        color = GREEN if is_online else GRAY
        
        print(" " * 5 + f"#{i} {color}{client_name}#{client_id}{RESET}")
    
    print()


def list_big():
    """Grid view (5 columns)"""
    print("\n" + " " * 5 + "List of clients (grid view):")
    print(" " * 5 + f"{GRAY}{'─' * 120}{RESET}")
    
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
    
    # Format clients
    formatted_clients = []
    for i, client in enumerate(clients, 1):
        client_id = client.get("ID", "?")
        client_name = client.get("NAME", "Unknown")
        
        is_online = client_id in online_ids
        color = GREEN if is_online else GRAY
        
        formatted_clients.append(f"#{i} {color}{client_name}#{client_id}{RESET}")
    
    # Display in 5 columns
    num_cols = 5
    for i in range(0, len(formatted_clients), num_cols):
        row = formatted_clients[i:i + num_cols]
        print(" " * 5 + "   ".join(row))
    
    print()