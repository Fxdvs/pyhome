import json
import os
import threading
import socket
from utils.colors import GREEN, RED, RESET
from utils.config import get_config
from utils.console import print_message

CLIENTS_FILE = "data/clients.json"

server_info = {
    "id": get_config("ID"),
    "name": get_config("NAME"),
    "type": get_config("TYPE"),
    "version": get_config("VERSION"),
    "host": get_config("HOST"),
    "port": get_config("PORT"),
}

# global vars
connected_clients = {}
clients_lock = threading.Lock()

# handle client
def handle_client(conn, addr):
    client_name = None
    client_id = None
    try:
        client_data = conn.recv(1024).decode("utf-8")
        if not client_data:
            return

        try:
            client_info = json.loads(client_data)
            client_id = client_info.get("id", "unknown")
            client_name = client_info.get("name", "unknown")
        except json.JSONDecodeError:
            client_name = client_data
            client_id = "unknown"

        with clients_lock:
            connected_clients[addr] = {"name": client_name, "id": client_id, "socket": conn}

        save_client(addr, client_name, client_id)
        print_message(f"Client {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET} has connected")

        # send server info
        conn.send(json.dumps(server_info).encode("utf-8"))

        # receive messages
        while True:
            try:
                conn.settimeout(1)  
                data = conn.recv(1024)
                if not data:
                    continue #  client doesnt disconnect
                message = data.decode("utf-8")
                print_message(f"From client {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET}: {message}")
            except socket.timeout:
                continue  # ignore timeout
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} has disconnected unexpectedly")
                break
            except Exception as e:
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} had an unexpected error: {e}")
                break
    except Exception as e:
        print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} had a fatal error: {e}")

    finally:
        with clients_lock:
            if addr in connected_clients:
                client_info = connected_clients[addr]
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} has disconnected")
                del connected_clients[addr]
        conn.close()

# save client
def save_client(addr, client_name, client_id):
    client_data = {
        "ID": client_id,
        "NAME": client_name
    }

    # load existing clients
    clients = []
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, "r") as f:
            try:
                clients = json.load(f)
            except json.JSONDecodeError:
                clients = []

    # update or add client
    updated = False
    for i, c in enumerate(clients):
        if c.get("ID") == client_id:
            clients[i] = client_data
            updated = True
            break

    if not updated:
        clients.append(client_data)

    # save to .json
    with open(CLIENTS_FILE, "w") as f:
        json.dump(clients, f, indent=4)