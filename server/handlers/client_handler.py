import json
import os
import asyncio
from utils.colors import GREEN, RED, RESET
from utils.config import get_config
from utils.console import print_message

CLIENTS_FILE = "data/clients.json"

server_info = {
    "id": get_config("ID"),
    "name": get_config("NAME"),
    "type": get_config("TYPE"),
    "version": get_config("VERSION"),
    "host": get_config("HOST"),
    "port": get_config("PORT"),
}

# global vars
connected_clients = {}
clients_lock = asyncio.Lock()

async def handle_client_async(reader, writer):
    addr = writer.get_extra_info('peername')
    client_name = None
    client_id = None
    
    try:
        # get client data
        data = await reader.read(1024)
        client_data = data.decode("utf-8")
        
        if not client_data:
            writer.close()
            await writer.wait_closed()
            return
        
        # parse json
        try:
            client_info = json.loads(client_data)
            client_id = client_info.get("id", "unknown")
            client_name = client_info.get("name", "unknown")
        except json.JSONDecodeError:
            client_name = client_data
            client_id = "unknown"
        
        # store client
        async with clients_lock:
            connected_clients[addr] = {
                "name": client_name,
                "id": client_id,
                "writer": writer
            }
        
        save_client(addr, client_name, client_id)
        print_message(f"Client {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET} has connected")
        
        # send information about server
        writer.write(json.dumps(server_info).encode("utf-8"))
        await writer.drain()
        
        # receive messages
        while True:
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                
                if not data:
                    break
                
                message = data.decode("utf-8")
                print_message(f"From client {GREEN}{addr[0]}:{addr[1]}@{client_name}#{client_id}{RESET}: {message}")
                
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
    
    except Exception as e:
        print_message(f"Client {RED}{addr}@{client_name}#{client_id}{RESET} had a fatal error: {e}")
    
    finally:
        # remove client
        async with clients_lock:
            if addr in connected_clients:
                client_info = connected_clients[addr]
                print_message(f"Client {RED}{addr[0]}:{addr[1]}@{client_info['name']}#{client_info['id']}{RESET} has disconnected")
                del connected_clients[addr]
        
        writer.close()
        await writer.wait_closed()


def save_client(addr, client_name, client_id):
    client_data = {"ID": client_id, "NAME": client_name}
    clients = []
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, "r") as f:
            try:
                clients = json.load(f)
            except json.JSONDecodeError:
                clients = []
    
    # update or add
    updated = False
    for i, c in enumerate(clients):
        if c.get("ID") == client_id:
            clients[i] = client_data
            updated = True
            break
    
    if not updated:
        clients.append(client_data)
    
    with open(CLIENTS_FILE, "w") as f:
        json.dump(clients, f, indent=4)


# number of connected clients
def get_connected_clients():
    return connected_clients

# lock
def get_clients_lock():
    return clients_lock