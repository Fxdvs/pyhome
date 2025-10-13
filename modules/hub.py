import json
import socket
import threading
import os
from time import sleep
from utils.colors import GREEN, RED, RESET
from utils.check_connection import is_connected
from utils.commands import commands

NAME = "Hub"
VERSION = "0.1"
HOST = '0.0.0.0'  
PORT = 5555      

os.system('color')

# global array of connected clients
connected_clients = {}
clients_lock = threading.Lock()

def handle_client(conn, addr):
    # Handles client connection
    module_name = None
    try:
        # Receive module name
        client_name = conn.recv(1024).decode('utf-8')
        if not client_name:
            return
        with clients_lock:
            connected_clients[addr] = client_name
        print(f"\nClient connected: {GREEN}{addr[0]}:{addr[1]}@{client_name}{RESET}")
        server_info = {
            "name": NAME,
            "version": VERSION,
            "host": HOST,
            "port": PORT
        }
        conn.send(json.dumps(server_info).encode('utf-8'))
        # Keep connection alive
        while True:
            try:
                conn.settimeout(5)
                data = conn.recv(1024)
                if not data:
                    break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error with {client_name}: {e}")
                break
    except Exception as e:
        print(f"{RED}Fatal error {addr}: {e}{RESET}")
    finally:
        # remove client from array
        with clients_lock:
            if addr in connected_clients:
                print(f"Client disconnected: {RED}{addr[0]}:{addr[1]}@{connected_clients[addr]}{RESET}")
                del connected_clients[addr]
        conn.close()

# main server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print(f"{NAME} is running on {HOST}:{PORT}")

def command_handler():
    # Command handler
    while True:
        match input("> ").strip().lower():
            case "list":
                with clients_lock:
                    if connected_clients:
                        print("\n" + " " * 5 + "List of connected clients")
                        for i, (client_addr,client_name) in enumerate(connected_clients.items(), 1):
                            print(" " * 5 + f"#{i} {GREEN}{client_addr[0]}:{client_addr[1]}@{client_name}{RESET}")
                        print()
                    else:
                        print("No connected clients\n")
            case "clear" | "cls":
                os.system('cls' if os.name == 'nt' else 'clear')
            case "exit":
                print(f"{RED}{NAME} is shutting down.{RESET}")  
                sleep(1)  
                exit(0)
            case "help" | "commands" | "?":
                print("\n" + " " * 5 + "List of Commands") 
                for cmd in commands:
                    print(" " * 5 + f"{cmd['name']} - {cmd['description']}  ")
            case "info" | "self" | "about":
                internet_status = f"{GREEN}True{RESET}" if is_connected() else f"{RED}False{RESET}"
                print("\n" + " " * 5 + f"Information")
                print(" " * 5 + f"Name: {NAME}") 
                print(" " * 5 + f"Host: {HOST}")
                print(" " * 5 + f"Port: {PORT}")
                print(" " * 5 + f"Version: {VERSION}")
                print(" " * 5 + f"Connected: {internet_status}")
                print(" " * 5 + f"Connected clients: {len(connected_clients)}")
            case "":
                pass
            case _:
                print(f"Unknown command. Type 'help | commands | ?' for list of commands.\n")

# Start server command thread
server_cmd_thread = threading.Thread(target=command_handler)
server_cmd_thread.daemon = True
server_cmd_thread.start()

try:
    while True:
        conn, addr = server_socket.accept()
        # Start new thread for each client
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.daemon = True
        client_thread.start()
except KeyboardInterrupt:
    print(f"\n{RED}{NAME} is turned off.{RESET}")
finally:
    server_socket.close()