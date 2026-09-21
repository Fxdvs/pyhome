"""Access to data/config.json.

The server and the client each have their own config file, so the app tells
this module where its own data folder is by calling init() on startup. Any
other config file can be chosen with --config, which is how one checkout runs
several clients.
"""
import json
import os
import sys
from uuid import uuid4

from shared.symbols import ERROR

_config_path = None
_config_cache = None


def init(app_dir, config_file=None):
    """Point the module at the config file. Called from app.py.

    config_file overrides the default <app_dir>/data/config.json.
    """
    global _config_path, _config_cache
    _config_path = config_file or os.path.join(app_dir, "data", "config.json")
    _config_cache = None


def config_file_from_argv(argv):
    """The absolute path given after --config, or None when there is none.

    Exits with a message when the value is missing or the file does not
    exist, running on an empty config would only fail later and less clearly.
    """
    if "--config" not in argv:
        return None

    index = argv.index("--config")
    if index + 1 >= len(argv):
        sys.exit(f"{ERROR} --config needs a file name")

    path = os.path.abspath(argv[index + 1])
    if not os.path.isfile(path):
        sys.exit(f"{ERROR} Config file not found: {path}")
    return path


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

    # a new config only needs NAME, the first run stamps its own identity
    if not _config_cache.get("ID"):
        rest = {k: v for k, v in _config_cache.items() if k != "ID"}
        save_config({"ID": uuid4().hex[:8], **rest})
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
