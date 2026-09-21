"""Access to data/config.json.

The server and the client each have their own config file, so the app tells
this module where its own data folder is by calling init() on startup.
"""
import json
import os

from shared.symbols import ERROR

_config_path = None
_config_cache = None


def init(app_dir):
    """Point the module at <app_dir>/data/config.json. Called from app.py."""
    global _config_path, _config_cache
    _config_path = os.path.join(app_dir, "data", "config.json")
    _config_cache = None


def get_config_path():
    if _config_path is None:
        raise RuntimeError("config.init() was never called")
    return _config_path


def load_config(reload=False):
    global _config_cache
    if _config_cache is not None and not reload:
        return _config_cache

    path = get_config_path()
    if not os.path.exists(path):
        print(f"{ERROR} Config file not found: {path}")
        _config_cache = {}
        return _config_cache

    with open(path, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
    return _config_cache


def save_config(config):
    global _config_cache
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    _config_cache = config


def get_config(key, default=None):
    return load_config().get(key, default)


def set_config(key, value):
    config = dict(load_config())
    config[key] = value
    save_config(config)
