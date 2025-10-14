import sys
import os

# get absolute path to project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
shared_utils = os.path.join(project_root, "utils")

# add shared utils folder to sys.path
if shared_utils not in sys.path:
    sys.path.insert(0, shared_utils)

# now import from shared utils
from colors import GREEN, RED, GRAY, RESET # type: ignore
from commands import commands # type: ignore

__all__ = ["GREEN", "RED", "GRAY", "RESET", "commands"]
