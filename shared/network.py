import errno
import os
import socket

# windows reports a taken port as winsock error 10048, not as errno.EADDRINUSE
_ADDRESS_IN_USE = {errno.EADDRINUSE, 10048}


def get_connection():
    """True when the machine can reach the internet."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


def get_local_ip():
    """The address this machine has on the local network.

    Opening a UDP socket sends nothing, it only makes the OS pick the
    interface it would route through, which is the address other devices
    in the house can reach.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def is_address_in_use(error):
    """True when an OSError means the port is taken, on any system."""
    return isinstance(error, OSError) and (
        error.errno in _ADDRESS_IN_USE or getattr(error, "winerror", None) == 10048)


def port_in_use_message(port, what):
    """What to print when port is taken, with the command that finds who has it."""
    if os.name == "nt":
        find = f"netstat -ano | findstr :{port}"
    else:
        find = f"lsof -i :{port}"
    return (f"Port {port} for the {what} is already in use, probably by another pyhome server.\n"
            f"  Find it with: {find}")


def check_port_free(host, port):
    """Bind and release host:port, raising the OSError a real bind would. Checks before starting."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # on posix a port in TIME_WAIT is free for a real server, which sets this too;
        # on windows the same flag would let two sockets share a port, so not there
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
    finally:
        s.close()
