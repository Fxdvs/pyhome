import asyncio
import json
from utils.config import get_config
from utils.colors import GREEN, RED, RESET

HOST = get_config("HOST")
PORT = get_config("PORT")
NAME = get_config("NAME")
ID = get_config("ID")

# global vars
CONNECTED = False
reader = None
writer = None
server_info = {}
connection_lock = asyncio.Lock()
auto_reconnect = False

async def connect_to_server_async():
    global CONNECTED, reader, writer, server_info, auto_reconnect
    tried_first = False
    while True:
        try:
            if not tried_first:
                print("Attempting first connection...")
                tried_first = True
            else:
                if not auto_reconnect:
                    await asyncio.sleep(1)
                    continue
            
            async with connection_lock:
                if not CONNECTED:
                    # Connect to server
                    reader, writer = await asyncio.open_connection(HOST, PORT)
                    
                    # Send client info
                    client_info = json.dumps({"id": ID, "name": NAME})
                    writer.write(client_info.encode('utf-8'))
                    await writer.drain()
                    
                    # Receive server info
                    server_data = await reader.read(1024)
                    server_info = json.loads(server_data.decode('utf-8'))
                    
                    CONNECTED = True
                    auto_reconnect = False
                    
                    print(f"\nConnected to {GREEN}{server_info['host']}:{server_info['port']}@{server_info['name']}#{server_info['id']}{RESET}")
        
        except ConnectionRefusedError:
            async with connection_lock:
                CONNECTED = False
            
            print("Server unavailable or missing.")
            # Ask user (in real scenario, you'd handle this better) todo
            auto_reconnect = True
            await asyncio.sleep(15)
        
        except Exception as e:
            async with connection_lock:
                CONNECTED = False
            print(f"Fatal error: {e}")
            await asyncio.sleep(15)


def get_connection_state():
    """Get connection state"""
    return CONNECTED, reader, writer, server_info


def get_connection_lock():
    """Get connection lock"""
    return connection_lock


def set_auto_reconnect(value):
    """Set auto reconnect flag"""
    global auto_reconnect
    auto_reconnect = value


def set_connected(value):
    """Set connected flag"""
    global CONNECTED
    CONNECTED = value