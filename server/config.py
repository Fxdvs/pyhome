import os
import json

from utils import GREEN, GRAY, RESET
path = os.path.join(os.path.dirname(__file__), "config.json")

with open(path, "r", encoding="utf-8") as f:
    config = json.load(f)
ID = config["ID"]
NAME = config["NAME"]
TYPE = config["TYPE"]
VERSION = config["VERSION"]
HOST = config["HOST"]
PORT = config["PORT"]

def handle_edit_name(name):
    global NAME
    FROM = NAME
    NAME = name
    config["NAME"] = name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    gap = 50
    print("\n" + " " * 5 + f"{GREEN}{NAME}@{ID}{RESET} has been changed.")
    print(" " * 5 + f"{GRAY}{'─' * gap}{RESET}")
    print(" " * 5 + f"{'Type:'.ljust(gap-len(TYPE))} {TYPE}")
    print(" " * 5 + f"{'From:'.ljust(gap-len(FROM))} {GRAY}{FROM}{RESET}")
    print(" " * 5 + f"{'To:'.ljust(gap-len(NAME))} {GREEN}{NAME}{RESET}")
    print("\n" +" " * 5 + "To check changes, open config.json")
    FROM = None