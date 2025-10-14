import json
import os
import random
import socket
import time
import threading
from utils.commands import commands
from utils.colors import GREEN, RED, YELLOW, RESET

NAME = "LED"
VERSION = "0.1"
HOST = '127.0.0.1'
PORT = 5555

CONNECTED = False
s = None
server_info = {}
connection_lock = threading.Lock()
auto_reconnect = False

os.system('color')
os.system(f"title {NAME}")

def connect_to_server():
    global CONNECTED, s, server_info, auto_reconnect
    while True:
        try:
            with connection_lock:
                if not CONNECTED:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.bind((HOST, random.randint(50000, 50050)))
                    s.connect((HOST, PORT))
                    s.send(NAME.encode('utf-8'))
                    server_data = s.recv(1024).decode('utf-8')
                    server_info = json.loads(server_data)
                   
                    CONNECTED = True
                    print(f"\nConnected to {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}")
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
                print(f"Server/Hub unavailable, auto-reconnecting in 15 seconds...{RESET}")
            else:
                print(f"Server/Hub unavailable or missing, retrying in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"Fatal error: {e}")
            time.sleep(15)

def command_handler():
    global s, CONNECTED, auto_reconnect
    while True:
        try:
            with connection_lock:
                is_connected = CONNECTED
            if is_connected:
                match input("> ").strip().lower():
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
                    case "":
                        pass
                    case _:
                        if cmd:
                            s.send(cmd.encode('utf-8'))
            else:
                print("Client not connected. Missing or unavailable server/hub.")
                print(f"Type 'q' to cancel auto-reconnect")
                
                cmd = input("> ").strip().lower()
                if cmd == "q":
                    with connection_lock:
                        auto_reconnect = False
                    print("Auto-reconnect cancelled.")
        except Exception as e:
            print(f"Error sending command: {e}")
            with connection_lock:
                CONNECTED = False
           
# Start connection thread
connect_thread = threading.Thread(target=connect_to_server)
connect_thread.daemon = True
connect_thread.start()

# Start command thread
try:
    command_handler()
except KeyboardInterrupt:
    print("\nClient shutdown")
finally:
    if s:
        s.close()