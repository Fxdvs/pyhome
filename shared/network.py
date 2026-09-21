import socket


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
