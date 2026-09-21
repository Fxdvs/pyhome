import json
import os

from utils.symbols import ERROR

# absolute, so the app works no matter which directory it was started from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "data", "config.json")

# the file is only read from disk once, set_config keeps this in sync
_config_cache = None

def load_config(reload=False):
    global _config_cache
    if _config_cache is not None and not reload:
        return _config_cache

    if not os.path.exists(CONFIG_PATH):
        print(f"{ERROR} Config file not found: {CONFIG_PATH}")
        _config_cache = {}
        return _config_cache

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
    return _config_cache

def save_config(config):
    global _config_cache
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    _config_cache = config

def get_config(key, default=None):
    return load_config().get(key, default)

def set_config(key, value):
    config = dict(load_config())
    config[key] = value
    save_config(config)
