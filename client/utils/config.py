import json
import os

from utils.symbols import ERROR

CONFIG_PATH = "data/config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"{ERROR} Config file not found: {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

def get_config(key, default=None):
    config = load_config()
    return config.get(key, default)

def set_config(key, value):
    config = load_config()
    config[key] = value
    save_config(config)



