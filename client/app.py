import json
import os
import socket
import time
import threading
from datetime import datetime

from utils import GREEN, RED, GRAY, RESET, commands
from config import ID, NAME, VERSION, HOST, PORT, handle_edit_name

# init
os.system('color')
os.system(f"title {NAME} {VERSION}")

# global variables
CONNECTED = False
s = None
server_info = {}
connection_lock = threading.Lock()
auto_reconnect = False

# connect to server
def connect_to_server():
    global CONNECTED, s, server_info, auto_reconnect
    tried_first = False
    while True:
        try:
            if not tried_first and not auto_reconnect:
                print("Attempting first connection...")
                tried_first = True
            else:
                # ak sa kód sem dostane, znamená to, že už bol reconnect
                if not auto_reconnect:
                    time.sleep(1)
                    continue

            with connection_lock:
                if not CONNECTED:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.connect((HOST, PORT))
                    
                    client_info = json.dumps({"id": ID, "name": NAME})
                    s.send(client_info.encode('utf-8'))
                    
                    server_data = s.recv(1024).decode('utf-8')
                    server_info = json.loads(server_data)
                    
                    CONNECTED = True
                    auto_reconnect = False
                    print(f"\nConnected to {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}#{server_info['id']}{RESET}")

        except ConnectionRefusedError:
            with connection_lock:
                CONNECTED = False

            print("Server unavailable or missing.")
            user_choice = input("Do you want to reconnect? (yes/no) > ").strip().lower()
            if user_choice in ["yes", "y"]:
                print("Attempting to reconnect...")
                auto_reconnect = True
                time.sleep(3)
                continue
            else:
                print("Staying offline. You can type 'reconnect' later.")
                auto_reconnect = False
                break

        except Exception as e:
            with connection_lock:
                CONNECTED = False
            print(f"Fatal error: {e}")
            time.sleep(15)

# receive messages
def receive_messages():
    # recieve messages from server
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
                    print(f"\nfrom {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET} {message}")
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


# edit name
def edit_name():
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
        print("\n" + " " * 5 + "Edit client name")
        print(" " * 5 + f"{GRAY}{'─' * gap}{RESET}")
        print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
        print(" " * 5 + f"{'From:'.ljust(gap-len(NAME))}{GRAY}{NAME}{RESET}")
        print(" " * 5 + f"{'To:'.ljust(gap-len(new_name))}{GREEN}{new_name}{RESET}\n")
        
        # potvrdenie zmeny
        prompt = f"Change from {NAME} to {new_name}? (y/n)"
        print(" " * 5 + f"{prompt.ljust(gap)}")  # zarovnanie promptu do gap
        accept = input(f">").strip().lower()
        if accept == "y":
            handle_edit_name(new_name)
        else:
            return 
        
        # aktualizácia názvu v okne
        try:
            from config import NAME, ID, VERSION
            os.system(f"title {NAME}#{ID} {VERSION}")
        except Exception as e:
            print(f"Error updating name: {e}")
    print("")

# about | self
def self():
    gap=70
    time = datetime.now().strftime("[%Y:%d:%m:%H:%M:%S]")
    try:
        from config import ID, NAME, TYPE, VERSION, HOST, PORT
        name = f"{NAME}@{ID}"
        print("\n" + " " * 5 + f"{name.ljust(gap - len(time))}{time}")
        print(" " * 5 + f"{GRAY}{'─' * gap}{RESET} ")
        print(" " * 5 + f"{'Name:'.ljust(gap-len(NAME))}{NAME}")
        print(" " * 5 + f"{'ID:'.ljust(gap-len(ID))}{ID}")
        print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))}{TYPE}")
        print(" " * 5 + f"{'Version:'.ljust(gap-len(VERSION))}{VERSION}")
        print(" " * 5 + f"{'Host/Adress:'.ljust(gap-len(HOST))}{HOST}")
        print(" " * 5 + f"{'Port:'.ljust(gap-len(str(PORT)))}{PORT}")
    except Exception as e:
        print(f"Error loading config: {e}")
    is_connected = CONNECTED
    if is_connected:
        print(" " * 5 + f"Connected: {GREEN}True{RESET}\n")
        print(" " * 5 + f"About {GREEN}{server_info.get('host')}:{server_info.get('port')}:{server_info.get('name')}#{server_info.get('id')}{RESET}")
        print(" " * 5 + f"{GRAY}{'─' * gap}{RESET} ")
        print(" " * 5 + f"{'Name:'.ljust(gap-2-len(server_info.get('name', 'unknown')))}")
        print(" " * 5 + f"Host: {server_info.get('host', 'Unknown')}")
        print(" " * 5 + f"Port: {server_info.get('port', 'Unknown')}")
        print(" " * 5 + f"Version: {server_info.get('version', 'Unknown')}\n")
    else:
        print(" " * 5 + f"Connected: {RED}False{RESET}")
        print("")

# send message - send
def send_message():
    # send message to server
    global s, CONNECTED
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
                    print(f"Error sending message: {e}")
                    CONNECTED = False
    else:
        print("No message sent")

# command handler
def command_handler():
    # Process user input commands
    global s, CONNECTED, auto_reconnect
    if not CONNECTED:
        print("Client not connected. Missing or unavailable server.")
        print("Type 'reconnect' to reconnect or 'exit' to quit")
    while True:
        try:
            cmd = input("> ").strip().lower()
            match cmd:
                case "clear" | "cls":
                    os.system('cls' if os.name == 'nt' else 'clear')
                case "disconnect" | "dc":
                    with connection_lock:
                        CONNECTED = False
                        auto_reconnect = False
                    if s:
                        s.close()
                    print("Disconnected from server.")
                case "edit name":
                    edit_name()
                case "exit" | "quit":
                    print(f"> {RED}{NAME}@{ID}{RESET} is shutting down.")
                    exit(0)   
                case "help" | "commands" | "?":
                    print("\n" + " " * 5 + f"{'Name of Command'.ljust(45)}Description", end="")
                    print("\n" + " " * 5 + f"{GRAY}─{RESET}" * 90)

                    for command in commands:
                        if command["type"] == "client" or command["type"] == "client/server":
                            print(" " * 5 + f"{command['name'].ljust(45)}{command['description']}")
                    print()
                case "list":
                    if not CONNECTED:
                        print("\n" + " " * 5 + "Not connected to server")
                        print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
                        print(" " * 5 + f"For connecting to server type 'reconnect'\n")
                    else:
                        print("\n" + " " * 5 + "Connected to server")
                        print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
                        print(" " * 5 + f"{GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}{RESET}\n")
                case "reconnect":
                    with connection_lock:
                        CONNECTED = False
                        auto_reconnect = True
                    if s:
                        s.close()
                        auto_reconnect = True
                        os.system('cls')
                        print("\n" + " " * 5 + "Reconnect")
                        print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
                        print(" " * 5 + f"Reconnecting to {server_info['host']}:{server_info['port']}@{server_info['name']}\n")
                        time.sleep(3) 
                    threading.Thread(target=connect_to_server, daemon=True).start()                
                case "self" | "about":
                    self()                
                case "send":
                    send_message()
                case "":
                    continue
                case _:
                    print("Unknown command. Type 'help | commands | ?' for list of commands.")
        except Exception as e:
            print(f"Error in command handler: {e}")
            with connection_lock:
                CONNECTED = False


# main
if __name__ == "__main__":
    # start connection thread
    connect_thread = threading.Thread(target=connect_to_server)
    connect_thread.daemon = True
    connect_thread.start()
    
    # Start receive thread
    receive_thread = threading.Thread(target=receive_messages)
    receive_thread.daemon = True
    receive_thread.start()
    
    # Start command handler
    try:
        command_handler()
    except KeyboardInterrupt:
        print("\nClient shutdown")
    finally:
        if s:
            s.close()