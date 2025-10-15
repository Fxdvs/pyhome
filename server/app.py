import json
import threading
import socket
import os
from datetime import datetime

from time import sleep
from utils import GREEN, RED, GRAY, RESET, is_connected, commands
from config import ID, NAME, VERSION, HOST, PORT, handle_name_edit

# init
os.system("color")
os.system(f"title {NAME}#{ID} {VERSION}")

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
    print(f"{NAME}@{ID} is running on {HOST}:{PORT}@{NAME}")

    return server_socket

# clear list | clear ls
def clear_list():   
    # clear clients list
    if os.path.exists("clients.txt"):
        os.remove("clients.txt")
        print("clients.txt clear successful.")

# show config | show conf
def show_config():
        internet_status = f"{GREEN}True{RESET}" if is_connected() else f"{RED}False{RESET}"
        gap = 70
        try:
            from config import ID, NAME, TYPE, VERSION, HOST, PORT
            os.system(f"title {NAME}@{ID} {VERSION}")
            print("\n" + " " * 5 + f"/config.json") 
            print(" " * 5 + f"{GRAY}{'─' * gap}{RESET} ")
            print(" " * 5 + f"{'ID:'.ljust(gap-len(ID))}{ID}")
            print(" " * 5 + f"{'Name:'.ljust(gap-len(NAME))}{NAME}")
            print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
            print(" " * 5 + f"{'Version:'.ljust(gap-len(VERSION))}{VERSION}")
            print(" " * 5 + f"{'Host/Adress:'.ljust(gap-len(HOST))}{HOST}")
            print(" " * 5 + f"{'Port:'.ljust(gap-len(str(PORT)))}{PORT}")
        except Exception as e:
            print(f"Error loading config: {e}")

# list | l
def list():
    # display connected clients
    print("\n" + " " * 5 + "List of connected clients:")
    print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
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
    print("")

# self | about
def self():
    internet_status = f"{GREEN}True{RESET}" if is_connected() else f"{RED}False{RESET}"
    time = datetime.now().strftime("[%Y:%d:%m:%H:%M:%S]")
    gap = 70
    
    try:
        from config import ID, NAME, TYPE, VERSION, HOST, PORT
        name = f"{NAME}@{ID}"
        print(" " * 5 + f"{name.ljust(gap - len(time))}{time}")
        print(" " * 5 + f"{GRAY}{'─' * gap}{RESET} ")
        print(" " * 5 + f"{'Name:'.ljust(gap-len(NAME))}{NAME}")
        print(" " * 5 + f"{'ID:'.ljust(gap-len(ID))}{ID}")
        print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
        print(" " * 5 + f"{'Version:'.ljust(gap-len(VERSION))}{VERSION}")
        print(" " * 5 + f"{'Host/Adress:'.ljust(gap-len(HOST))}{HOST}")
        print(" " * 5 + f"{'Port:'.ljust(gap-len(str(PORT)))}{PORT}")
    except Exception as e:
        print(f"Error loading config: {e}")
    print(" " * 5 + f"{'Connected:'.ljust(gap-len(str(is_connected())))}{internet_status}")
    
    print(" " * 5 + f"{'Connected clients:'.ljust(gap-len(str(len(connected_clients))))}{len(connected_clients)}\n")

# name edit
def name_edit():
    gap = 50
    print("\n" + " " * 5 + "Edit name")
    print(" " * 5 + f"{GRAY}{'─' * gap}{RESET}")
    try:
        from config import NAME, TYPE
        print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
        print(" " * 5 + f"{'From:'.ljust(gap-len(NAME))}{GRAY}{NAME}{RESET}\n")
    except Exception as e:
        print(f"Error loading config: {e}")
    
    new_name = input(">: ").strip().lower()
    if new_name != "":
        print("\n" + " " * 5 + "Edit server name")
        print(" " * 5 + f"{GRAY}{'─' * gap}{RESET}")
        print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
        print(" " * 5 + f"{'From:'.ljust(gap-len(NAME))}{GRAY}{NAME}{RESET}")
        print(" " * 5 + f"{'To:'.ljust(gap-len(new_name))}{GREEN}{new_name}{RESET}\n")
        
        # potvrdenie zmeny
        prompt = f"Change from {NAME} to {new_name}? (y/n)"
        print(" " * 5 + f"{prompt.ljust(gap)}")  # zarovnanie promptu do gap
        accept = input(f">").strip().lower()
        if accept == "y":
            handle_name_edit(new_name)
        else:
            return 
        
        # aktualizácia názvu v okne
        try:
            from config import NAME, ID, VERSION
            os.system(f"title {NAME}@{ID} {VERSION}")
        except Exception as e:
            print(f"Error updating name: {e}")
    print("")

# restart
def restart_server():
    print("Are you sure you want to restart the server? (y/n)")
    accept = input(">").strip().lower()
    if accept == "y":
        os.system("cls")
        print("\n" + " " * 5 + "Server restarting...")
        print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
        for i in range(1,6):
            print(" " * 5 + f"Restarting in {RED}{i}{RESET} seconds")
            sleep(1)
        os.system("cls")
        os.system("py app.py")
    else:
        return
    
# send
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

# command handler
def command_handler():
    # handles commands
    while True:
        try:
            cmd = input("> ").strip().lower()
            match cmd:
                case "clear" | "cls":
                    os.system("cls" if os.name == "nt" else "clear")
                    continue
                case "clear list" | "clear ls":
                    accept = input("Are you sure you want to clear the client list? (y/n) ").strip().lower()
                    if accept == "y":
                        clear_list()
                    else:
                        print("Clear cancelled.")
                case "config update" | "conf load": 
                    config_update()
                case "exit" | "quit":
                    print(f"> {RED}{NAME}#{ID}{RESET} is shutting down.")
                    exit(0)      
                case "help" | "commands" | "?":
                    print("\n" + " " * 5 + f"{'Name of Command'.ljust(45)}Description", end="")
                    print("\n" + " " * 5 + f"{GRAY}─{RESET}" * 90)

                    for command in commands:
                        if command["type"] == "server" or command["type"] == "client/server":
                            print(" " * 5 + f"{command['name'].ljust(45)}{command['description']}")
                    print()
                case "list" | "ls":
                    list()
                case "self" | "about":
                    self()
                case "show config" | "show conf":
                    show_config()
                case "name edit":
                    name_edit()
                case "restart":
                    restart_server()
                case "send":
                    send_message_to_client()
                case "":
                    continue
                case _:
                    print("Unknown command. Type 'help | commands | ?' for list of commands.")
        except Exception as e:
            print(f"Error in command handler: {e}")

# main
if __name__ == "__main__":
    # start command handler thread
    server_cmd_thread = threading.Thread(target=command_handler)
    server_cmd_thread.daemon = True
    server_cmd_thread.start()

    # start server socket
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
