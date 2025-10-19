import sys
import threading

# global var
print_lock = threading.Lock()

def print_message(message: str):
    with print_lock:
        # deletes the last line
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()
        
        # prints out the message
        print(message)
        
       # prints out the command handler
        sys.stdout.write(">")
        sys.stdout.flush()
