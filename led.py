import os
import socket
import time
import threading
from utils.colors import GREEN, RED, RESET

NAME = "LED"
VERSION = "0.1"
HOST = '127.0.0.1'
PORT = 5555
CONNECTED = False
s = None

os.system('color')

def connect_to_server():
    # Connects to server / hub
    
    global CONNECTED, s
    while True:
        try:
            if not CONNECTED:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((HOST, PORT))
                s.send(NAME.encode('utf-8'))
                CONNECTED = True
                print(f"Connected to {GREEN}{HOST}:{PORT}@{NAME}{RESET}")
            # Wait for command with timeout
            s.settimeout(1)
            try:
                data = s.recv(1024).decode('utf-8')
                if not data:
                    connected = False
                    print("Could not receive data, disconnected.")
            except socket.timeout:
                pass
            
        except ConnectionRefusedError:
            connected = False
            print(f"Server/Hub unavailable or missing, retrying in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            connected = False
            print(f"Fatal error: {e}")
            time.sleep(15)

def command_handler():
    global s, connected
    while True:
        try:
            if connected:
                cmd = input('>').strip().lower()
                match cmd:
                    case "clear" | "cls":
                        os.system('cls' if os.name == 'nt' else 'clear')
                    case "exit":
                        print(f"{NAME} is shutting down.")  
                        time.sleep(1)  
                        exit(0)
                    case "help":
                        print(f"List of Commands\nclear | cls - clears the console.\ninfo | self | about - information about the device \nexit - exits the server.")
                    case "info" | "self" | "about":
                        print(f"Name: {NAME} \nHost: {HOST}\nPort: {PORT} \nVersion: {VERSION}")  
                s.send(cmd.encode('utf-8'))
            else:
                print("Client can not connected. Missing or unavailable server/hub.")
                time.sleep(2)
        except Exception as e:
            print(f"Error sending command: {e}")
            connected = False
            
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