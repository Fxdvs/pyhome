import json
import os
import threading
import socket
from utils.colors import GREEN, RED, RESET
from utils.config import get_config

server_info = {
    "id": get_config("ID"),
    "name": get_config("NAME"),
    "type": get_config("TYPE"),
    "version": get_config("VERSION"),
    "host": get_config("HOST"),
    "port": get_config("PORT"),
}

# Globálna zdieľaná pre server
connected_clients = {}
clients_lock = threading.Lock()

# =========================
# Funkcie na správu klientov
# =========================
def handle_client(conn, addr):
    """Správa jednotlivého klienta"""
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
        print(f"\nClient connected {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET}")

        # Poslanie info klientovi
        conn.send(json.dumps(server_info).encode("utf-8"))

        # Udržiavanie spojenia
        while True:
            try:
                conn.settimeout(1)  # kratší timeout na recv
                data = conn.recv(1024)
                if not data:
                    continue  # nech klient ostane pripojený
                message = data.decode("utf-8")
                print(f"From {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET}: {message}")
            except socket.timeout:
                continue  # timeout ignorujeme, cyklus beží ďalej
            except Exception as e:
                print(f"{RED}Client {addr} error: {e}{RESET}")
                break

    except Exception as e:
        print(f"{RED}Fatal error {addr}: {e}{RESET}")
    finally:
        with clients_lock:
            if addr in connected_clients:
                client_info = connected_clients[addr]
                print(f"Client disconnected {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET}")
                del connected_clients[addr]
        conn.close()

# =========================
# Ukladanie klientov
# =========================
CLIENTS_FILE = "data/clients.json"
def save_client(addr, client_name, client_id):
    client_data = {
        "ID": client_id,
        "NAME": client_name
    }

    # načítanie existujúcich klientov
    clients = []
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, "r") as f:
            try:
                clients = json.load(f)
            except json.JSONDecodeError:
                clients = []

    # aktualizovanie existujúceho klienta podľa ID
    updated = False
    for i, c in enumerate(clients):
        if c.get("ID") == client_id:
            clients[i] = client_data
            updated = True
            break

    if not updated:
        clients.append(client_data)

    # uloženie do JSON súboru
    with open(CLIENTS_FILE, "w") as f:
        json.dump(clients, f, indent=4)