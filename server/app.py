import os
import threading

from utils.config import get_config
from handlers.server_handler import start_server
from handlers.command_handler import command_handler
from handlers.client_handler import handle_client

NAME = get_config("NAME")
ID = get_config("ID")
VERSION = get_config("VERSION")

# init app
os.system("color")
os.system(f"title {NAME}#{ID} {VERSION}")

# start server
if __name__ == "__main__":
    # start server socket
    server_socket = start_server()

    # command handler thread
    command_handler_thread = threading.Thread(target=command_handler)
    command_handler_thread.daemon = True
    command_handler_thread.start()

    # client handler thread
    try:
        # accept and handle client connections
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print(f"\n{NAME} is turned off.")
    finally:
        server_socket.close()
