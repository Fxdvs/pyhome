import sys
import os

# get absolute path of the shared utils folder
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared_utils = os.path.join(base_dir, "utils")

# add shared utils to sys.path if it's not already there
if shared_utils not in sys.path:
    sys.path.insert(0, shared_utils)

# explicitly import symbols from shared utils
from colors import GREEN, RED, GRAY, RESET # type: ignore
from commands import commands # type: ignore
from check_connection import is_connected  # type: ignore

# expose everything from this local utils.py
__all__ = ["GREEN", "RED", "RESET", "commands"]
 