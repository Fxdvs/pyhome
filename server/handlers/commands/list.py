import os

from utils.colors import GRAY, RESET

# list | ls
def list():
    # display connected clients
    print("\n" + " " * 5 + "List of connected clients")
    print(" " * 5 + f"{GRAY}{'─' * 50}{RESET}")
    if not os.path.exists("clients.txt"):
        print(" " * 5 + "No clients found")
        print("")
        return
    
    client_id = 1
    clients_found = False
    with open("clients.txt", "r") as f:
        for line in f:
            client_info = line.strip()
            if not client_info or "No connected clients" in client_info:
                continue
            clients_found = True
            
            # Check if client is online
            is_online = False
            with clients_lock:
                for addr, client_data in connected_clients.items():
                    # Support both old (string) and new (dict) format
                    if isinstance(client_data, dict):
                        client_name = client_data.get("name", "")
                        client_id_val = client_data.get("id", "")
                        online_key = f"{addr[0]}:{addr[1]}@{client_name}#{client_id_val}"
                    else:
                        online_key = f"{addr[0]}:{addr[1]}@{client_data}"
                    
                    if online_key in client_info or client_info.startswith(f"{addr[0]}:{addr[1]}@"):
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

# list -b | ls -b
def list_b():
    # display connected clients in columns
    print("\n" + " " * 5 + "List of connected clients")
    print(" " * 5 + f"{GRAY}{'─' * 120}{RESET}")
    
    if not os.path.exists("clients.txt"):
        print(" " * 5 + "No clients found\n")
        return
    
    clients = []
    
    with open("clients.txt", "r") as f:
        for line in f:
            client_info = line.strip()
            if not client_info or "No connected clients" in client_info:
                continue
            
            # Check if client is online
            is_online = False
            with clients_lock:
                for addr, client_data in connected_clients.items():
                    # Support both old (string) and new (dict) format
                    if isinstance(client_data, dict):
                        client_name = client_data.get("name", "")
                        client_id_val = client_data.get("id", "")
                        online_key = f"{addr[0]}:{addr[1]}@{client_name}#{client_id_val}"
                    else:
                        online_key = f"{addr[0]}:{addr[1]}@{client_data}"
                    
                    if online_key in client_info or client_info.startswith(f"{addr[0]}:{addr[1]}@"):
                        is_online = True
                        break
            
            color = GREEN if is_online else GRAY
            clients.append(f"{color}{client_info}{RESET}")
    
    if not clients:
        print(" " * 5 + "No clients found\n")
        return
    
    # 5 cols, 25 clients per col
    max_per_column = 25
    num_columns = 5
    columns = [clients[i:i + max_per_column] for i in range(0, len(clients), max_per_column)]
    
    # Same height for all columns
    max_height = max(len(col) for col in columns) if columns else 0
    for col in columns:
        while len(col) < max_height:
            col.append("")
    
    # Width of each column
    col_width = max(len(c.replace(GREEN, "").replace(GRAY, "").replace(RESET, "")) for c in clients) + 10 if clients else 30
    
    # Print by rows
    for row in range(max_height):
        row_str = " " * 5
        for col_idx, col in enumerate(columns):
            if row < len(col) and col[row]:
                client_id = row + 1 + (col_idx * max_per_column)
                entry = f"#{client_id:<3} {col[row]:<{col_width}}"
                row_str += entry
        print(row_str.rstrip())
    
    print("")