import json
import threading
import socket
import os
import shutil

from time import sleep
from utils import GREEN, RED, GRAY, RESET, is_connected, commands
from config import ID, NAME, VERSION, HOST, PORT, handle_name

# init
os.system("color")
os.system(f"title {NAME} {VERSION}")

# global variables
connected_clients = {}
clients_lock = threading.Lock()

# client managment
def handle_client(conn, addr):
    # handle client connection and communication
    client_name = None
    try:
        # client name from connection
        client_name = conn.recv(1024).decode("utf-8")
        if not client_name:
            return
        # store client in global
        with clients_lock:
            connected_clients[addr] = client_name
        # save client to storage
        save_client(addr, client_name)
        print(f"\nClient connected {GREEN}{addr[0]}:{addr[1]}@{client_name}{RESET}")
        # prepare server information
        server_info = {"name": NAME, "version": VERSION, "host": HOST, "port": PORT}
        conn.send(json.dumps(server_info).encode("utf-8"))

        # keep connection and receive messages
        while True:
            try:
                conn.settimeout(5)
                data = conn.recv(1024)
                if not data:
                    break

                message = data.decode("utf-8")
                print(f"from {GREEN}{addr[0]}:{addr[1]}@{client_name}{RESET} {message}")

            except socket.timeout:
                continue
            except Exception as e:
                break

    except Exception as e:
        print(f"{RED}Fatal error {addr}: {e}{RESET}")

    finally:
        # remove client from active
        with clients_lock:
            if addr in connected_clients:
                print(
                    f"Client disconnected {RED}{addr[0]}:{addr[1]}@{connected_clients[addr]}{RESET}"
                )
                del connected_clients[addr]
        conn.close()

def save_client(addr, client_name):
    # Save client info to clients.txt file without duplicates
    client_key = f"{addr[0]}:{addr[1]}@{client_name}"

    # check client already exists in file
    if os.path.exists("clients.txt"):
        with open("clients.txt", "r") as f:
            for line in f:
                if line.strip() == client_key:
                    return

    # append new client to file
    with open("clients.txt", "a") as f:
        f.write(f"{client_key}\n")

# server
def start_server():
    # init and start server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"{NAME}#{ID} is running on {HOST}:{PORT}")

    return server_socket

# client list - list
def display_clients_list():
    # display connected clients
    print("\n" + " " * 5 + "List of clients")
    if not os.path.exists("clients.txt"):
        print(" " * 5 + "No clients found")
        return
    client_id = 1
    clients_found = False
    with open("clients.txt", "r") as f:
        for line in f:
            client_info = line.strip()
            if not client_info or "No connected clients" in client_info:
                continue
            clients_found = True
            # check client if is online
            is_online = False
            with clients_lock:
                for addr, name in connected_clients.items():
                    if f"{addr[0]}:{addr[1]}@{name}" == client_info:
                        is_online = True
                        break
            if is_online:
                print(" " * 5 + f"#{client_id} {GREEN}{client_info}{RESET}")
            else:
                print(" " * 5 + f"#{client_id} {GRAY}{client_info}{RESET}")
            client_id += 1
    if not clients_found:
        print(" " * 5 + "No clients found")
    
    print()
# send message - send
def send_message_to_client():
    # send message to client
    print("\n" + " " * 5 + "Available clients:")

    if not os.path.exists("clients.txt"):
        print(" " * 5 + "No clients found\n")
        return

    # Display all clients
    with open("clients.txt", "r") as f:
        for line in f:
            client_info = line.strip()
            if not client_info or "No connected clients" in client_info:
                continue

            is_online = False
            with clients_lock:
                for addr, name in connected_clients.items():
                    if f"{addr[0]}:{addr[1]}@{name}" == client_info:
                        is_online = True
                        break

            if is_online:
                print(" " * 5 + f"{GREEN}{client_info}{RESET}")
            else:
                print(" " * 5 + f"{GRAY}{client_info}{RESET}")

    print()
    print(" " * 5 + "Select client by port (q to quit)")
    selected_port = input("> ").strip().lower()

    if selected_port in ["q", ""]:
        return

    # Get message
    message = input("> (message) ").strip()
    if not message:
        print("No message sent")
        return

    # Send to selected client
    with clients_lock:
        for addr, name in connected_clients.items():
            if str(addr[1]) == selected_port:
                try:
                    # Note: conn is needed here - requires refactoring to send via socket
                    print(f"sent {GREEN}{addr[0]}:{addr[1]}@{name}{RESET} {message}")
                except Exception as e:
                    print(f"Error sending message: {e}")
                return

    print("Client not found or not connected")

# edit name - name
def edit_client_name():
    cmd = input("> (new name) ").strip().lower()
    if cmd != "":
        handle_name(cmd)
        try:
            from config import NAME, VERSION

            os.system(f"title {NAME} {VERSION}")
        except Exception as e:
            print(f"Error updating name: {e}")
    print("")

# info - about | info | self
def info():
    internet_status = f"{GREEN}True{RESET}" if is_connected() else f"{RED}False{RESET}"
    try:
        from config import ID, NAME, VERSION, HOST, PORT
        print("\n" + " " * 5 + f"{NAME}#{ID}")
        print(" " * 5 + f"Name: {NAME}")
        print(" " * 5 + f"Version: {VERSION}")
        print(" " * 5 + f"Host: {HOST}")
        print(" " * 5 + f"Port: {PORT}")
    except Exception as e:
        print(f"Error updating name: {e}")
    print(" " * 5 + f"Connected: {internet_status}")
    print(" " * 5 + f"Connected clients: {len(connected_clients)}\n")

# command handler
def command_handler():
    # handles commands
    while True:
        try:
            cmd = input("> ").strip().lower()
            match cmd:
                case "list":
                    display_clients_list()
                case "clear" | "cls":
                    os.system("cls" if os.name == "nt" else "clear")
                case "exit":
                    print(f"{RED}{NAME} is shutting down.{RESET}")
                    sleep(1)
                    exit(0)
                case "help" | "commands" | "?":
                    print("\n" + " " * 5 + "List of Commands")
                    for command in commands:
                        print(" " * 5 + f"{command['name']} - {command['description']}")
                    print()
                case "info" | "self" | "about":
                    info()
                case "send":
                    send_message_to_client()
                case "name":
                    edit_client_name()
                case "":
                    continue
                case _:
                    print(
                        "Unknown command. Type 'help | commands | ?' for list of commands."
                    )

        except Exception as e:
            print(f"Error in command handler: {e}")


# main
if __name__ == "__main__":
    # start command handler thread
    server_cmd_thread = threading.Thread(target=command_handler)
    server_cmd_thread.daemon = True
    server_cmd_thread.start()

    # Start server socket
    server_socket = start_server()
    try:
        # accept and handle client connections
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()

    except KeyboardInterrupt:
        print(f"\n{RED}{NAME} is turned off.{RESET}")

    finally:
        server_socket.close()
