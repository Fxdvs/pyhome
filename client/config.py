import os
import json
from utils import GRAY, RESET
path = os.path.join(os.path.dirname(__file__), "config.json")

with open(path, "r", encoding="utf-8") as f:
    config = json.load(f)

NAME = config["NAME"]
TYPE = config["TYPE"]
ID = config["ID"]
VERSION = config["VERSION"]
HOST = config["HOST"]
PORT = config["PORT"]

def handle_edit_name(name):
    global NAME
    NAME = name
    config["NAME"] = name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"{GRAY}#{RESET} name change to {name} in config.json")
