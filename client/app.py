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

os.system('color')
os.system(f"title {NAME} {VERSION}")


def connect_to_server():
    global CONNECTED, s, server_info, auto_reconnect
    while True:
        try:
            with connection_lock:
                if not CONNECTED:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                    # Random port 50000-50050
                    client_port = random.randint(50000, 50050)
                    try:
                        s.bind(('127.0.0.1', client_port))
                    except OSError:
                        s.bind(('127.0.0.1', 0))
                    
                    s.connect((HOST, PORT))
                    s.send(NAME.encode('utf-8'))
                    server_data = s.recv(1024).decode('utf-8')
                    server_info = json.loads(server_data)

                    CONNECTED = True
                    print(f"\nConnected to {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}")
                    auto_reconnect = False
            
            # Keep connection alive
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
                print(f"Server unavailable, auto-reconnecting in 15 seconds...")
            else:
                print(f"Server unavailable or missing, retrying in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"Fatal error: {e}")
            time.sleep(15)


def receive_messages():
    global CONNECTED, s, server_info
    while True:
        try:
            with connection_lock:
                if not CONNECTED or s is None:
                    time.sleep(0.5)
                    continue
                sock = s
            
            try:
                sock.settimeout(0.5)
                data = sock.recv(1024)                
                if data:
                    message = data.decode('utf-8')
                    print(f"from {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
                    print("> ", end="", flush=True)
            except socket.timeout:
                pass
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                with connection_lock:
                    CONNECTED = False
                print(f"\n{RED}Connection lost{RESET}")
                break
        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"\n{RED}Error receiving: {e}{RESET}")
            time.sleep(1)


def command_handler():
    global s, CONNECTED, auto_reconnect
    while True:
        try:
            with connection_lock:
                is_connected = CONNECTED
            
            if is_connected:
                cmd = input("> ").strip().lower()
                
                match cmd:
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
                            auto_reconnect = True
                        if s:
                            s.close()
                        print("Attempting to reconnect...")
                    
                    case "exit":
                        print(f"{RED}{NAME} is shutting down.{RESET}")
                        time.sleep(1)
                        exit(0)
                    
                    case "help" | "commands" | "?":
                        print("\n" + " " * 5 + "List of Commands")
                        for command in commands:
                            print(" " * 5 + f"{command['name']} - {command['description']}")
                        print()
                    
                    case "info" | "self" | "about":
                        print("\n" + " " * 5 + "Information")
                        print(" " * 5 + f"Name: {NAME}")
                        print(" " * 5 + f"Host: {HOST}")
                        print(" " * 5 + f"Port: {PORT}")
                        print(" " * 5 + f"Version: {VERSION}")
                        print(" " * 5 + f"Connected: {GREEN}True{RESET}")
                        print(" " * 9 + f"Server Name: {server_info.get('name', 'Unknown')}")
                        print(" " * 9 + f"Server Host: {server_info.get('host', 'Unknown')}")
                        print(" " * 9 + f"Server Port: {server_info.get('port', 'Unknown')}")
                        print(" " * 9 + f"Server Version: {server_info.get('version', 'Unknown')}\n")
                    
                    case "send":
                        print("\n" + " " * 5 + "Connected server")
                        print(" " * 5 + f"{GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}\n")
                        message = input("> (message) ").strip()
                        if message:
                            print(f"> sent {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
                            with connection_lock:
                                if CONNECTED and s:
                                    try:
                                        s.send(message.encode('utf-8'))
                                    except Exception as e:
                                        print(f"Error sending: {e}")
                                        with connection_lock:
                                            CONNECTED = False
                        else:
                            print("No message sent")
                    
                    case "":
                        pass
                    
                    case _:
                        print("Unknown command. Type 'help | commands | ?' for list of commands.")
            
            else:
                print("Client not connected. Missing or unavailable server.")
                print(f"Type 'reconnect' to reconnect or 'exit' to quit")
                
                cmd = input("> ").strip().lower()
                if cmd == "reconnect":
                    with connection_lock:
                        auto_reconnect = True
                    print("Trying to reconnect...")
                elif cmd == "exit":
                    print(f"{RED}{NAME} is shutting down.{RESET}")
                    exit(0)
        
        except Exception as e:
            print(f"Error in command handler: {e}")
            with connection_lock:
                CONNECTED = False


# Start connection thread
connect_thread = threading.Thread(target=connect_to_server)
connect_thread.daemon = True
connect_thread.start()

# Start receive thread
receive_thread = threading.Thread(target=receive_messages)
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