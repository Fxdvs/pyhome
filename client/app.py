import json
import os
import random
import socket
import time
import threading
from utils import GREEN, RED, RESET, commands
from config import NAME, HOST, PORT
VERSION = "0.3"

CONNECTED = False
s = None
server_info = {}
connection_lock = threading.Lock()
auto_reconnect = False

global color_status 
color_status = os.system('color')

os.system(f"title {NAME} {VERSION}")

def connect_to_server():
    global CONNECTED, s, server_info, auto_reconnect
    while True:
        try:
            with connection_lock:
                if not CONNECTED:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.bind((HOST, random.randint(50000, 50050))) # random 50000 - 50050
                    s.connect((HOST, PORT))
                    s.send(NAME.encode('utf-8'))
                    server_data = s.recv(1024).decode('utf-8')
                    server_info = json.loads(server_data)

                    CONNECTED = True
                    print(
                        f"\nConnected to {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}")
                    auto_reconnect = False
            # Wait for command with timeout
            if CONNECTED:
                s.settimeout(1)
                try:
                    data = s.recv(1024).decode('utf-8')
                    if not data:
                        
                        with connection_lock:
                            CONNECTED = False
                        print("Could not receive data, disconnected.")

                except socket.timeout:
                    pass

        except ConnectionRefusedError:
            with connection_lock:
                CONNECTED = False
            if auto_reconnect:
                print(
                    f"server unavailable, auto-reconnecting in 15 seconds...{RESET}")
            else:
                print(f"server unavailable or missing, retrying in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"Fatal error: {e}")
            time.sleep(15)

def receive_messages():
    global CONNECTED, s
    while True:
        with connection_lock:
            if not CONNECTED or s is None:
                time.sleep(0.1)
                continue
            sock = s

        try:
            sock.settimeout(1)
            try:
                data = sock.recv(1024)
                if data:
                    data = data.decode('utf-8')
                    print(f"from {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {data}")
            except socket.timeout:
                pass
            except (ConnectionResetError, ConnectionAbortedError):
                with connection_lock:
                    CONNECTED = False
                print(f"{RED}Disconnected from server.{RESET}")
        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"Error receiving data: {e}")
            time.sleep(1)

            
def commands():
    match input("> ").strip().lower():
        case "list":
            print("\n" + " " * 5 + "Connected to server")
            print(" " * 5 + f"{GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}\n")
        case "clear" | "cls":
            os.system('cls' if os.name == 'nt' else 'clear')
        case "disconnect":
            with connection_lock:
                CONNECTED = False
                auto_reconnect = False
            if s:
                s.close()
            print("Disconnected from server.")
        case "reconnect":
            with connection_lock:
                CONNECTED = False
                auto_reconnect = False
            if s:
                s.close()
            print("Attempting to reconnect...")
        case "exit":
            print(f"{RED}{NAME} is shutting down.{RESET}")
            time.sleep(1)
            exit(0)
        case "help" | "commands" | "?":
            print("\n" + " " * 5 + "List of Commands")
            for cmd in commands:
                print(" " * 5 + f"{cmd['name']} - {cmd['description']}")
            print()
        case "info" | "self" | "about":
            print("\n" + " " * 5 + "Information")
            print(" " * 5 + f"Name: {NAME}")
            print(" " * 5 + f"Host: {HOST}")
            print(" " * 5 + f"Port: {PORT}")
            print(" " * 5 + f"Version: {VERSION}")
            print(" " * 5 + f"Connected: {GREEN}True{RESET}")
            print(" " * 9 + f" Name: {server_info.get('name', 'Unknown')}")
            print(" " * 9 + f" Host: {server_info.get('host', 'Unknown')}")
            print(" " * 9 + f" Port: {server_info.get('port', 'Unknown')}")
            print(" " * 9 + f" Version: {server_info.get('version', 'Unknown')}")
        case "send":
            print("\n" + " " * 5 + "Connected server") 
            print(f" " * 5 + f"{GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}\n")
            cmd = input(f"> (message) ").strip()
            if cmd:
                print(f"> sent {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {cmd}")
                s.send(cmd.encode('utf-8'))
            else: 
                print("Error sending message")
        case "color enable":
            color_status = os.system('color')
            print("Color restored.")
        case "color disable":
            color_status = os.system('color 0')
            print("Color disabled.")
        case "color":
            print("To enable color, type 'color enable'. To disable color, type 'color disable'.")
        case _:
            print("Unknown command. Type 'help | commands | ?' for list of commands.")

def command_handler():
    global s, CONNECTED, auto_reconnect
    while True:
        try:
            with connection_lock:
                is_connected = CONNECTED
            if is_connected:
                commands()
            else:
                print("Client not connected. Missing or unavailable server.")
                print(f"Type 'reconnect' to reconnect")

                cmd = input("> ").strip().lower()
                if cmd == "reconnect":
                    with connection_lock:
                        auto_reconnect = True
                    print("Trying to reconnect...")
        except Exception as e:
            print(f"Error sending command: {e}")
            with connection_lock:
                CONNECTED = False


# Start connection thread
connect_thread = threading.Thread(target=connect_to_server)
connect_thread.daemon = True
connect_thread.start()

# Start receive thread
receive_thread = threading.Thread(target=receive_messages, daemon=True)
receive_thread.daemon = True
receive_thread.start()

# Start command thread
try:
    command_handler()
except KeyboardInterrupt:
    print("\nClient shutdown")
finally:
    if s:
        s.close()
