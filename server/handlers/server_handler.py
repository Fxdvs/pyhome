import socket

from utils.symbols import SUCCESS
from utils.config import get_config

NAME = get_config("NAME")
ID = get_config("ID")
HOST = get_config("HOST")
PORT = get_config("PORT")

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"{SUCCESS} {NAME}#{ID} running on {HOST}:{PORT}")
    return server_socket