"""Access to data/config.json.

The server and the client each have their own config file, so the app tells
this module where its own data folder is by calling init() on startup. Any
other config file can be chosen with --config, which is how one checkout runs
several clients.
"""
import json
import os
import re
import sys
from uuid import uuid4

from shared.symbols import ERROR

_config_path = None
_config_cache = None

# room-device, what a person types in do and send: kuchyna-svetlo
ID_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# send all means every client, a client called all could never be picked alone
RESERVED_IDS = {"all"}


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


def id_from_file_name(path):
    """The id a config file's name gives, or None. kuchyna-svetlo.json -> kuchyna-svetlo.

    config.json gives None, the name says nothing about the device.
    """
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    if stem == "config" or stem in RESERVED_IDS or not ID_PATTERN.fullmatch(stem):
        return None
    return stem


def id_warning(value):
    """Why value makes a poor id, or None when it follows the rule. Never a refusal."""
    text = str(value)
    if text in RESERVED_IDS:
        return f"ID '{text}' is reserved for send all, choose another"
    if not ID_PATTERN.fullmatch(text):
        warning = f"ID '{text}' does not follow the id rule (a-z, 0-9 and -)"
        # the console splits arguments on whitespace, such an id can never be one
        if any(ch.isspace() for ch in text):
            warning += ", it cannot be typed in commands"
        return warning
    return None


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

    # a new config only needs NAME, the first run stamps its own identity,
    # taken from the file name when that is a usable id
    if not _config_cache.get("ID"):
        rest = {k: v for k, v in _config_cache.items() if k != "ID"}
        save_config({"ID": id_from_file_name(path) or uuid4().hex[:8], **rest})
    return _config_cache


def save_config(config):
    global _config_cache
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # the file is already utf-8, no need to escape it into \uXXXX
        json.dump(config, f, indent=4, ensure_ascii=False)
    _config_cache = config


def get_config(key, default=None):
    return load_config().get(key, default)


def get_config_file(key):
    """The absolute path a config key names, or None when it is empty.

    A relative path is taken from the config file's folder, so an instance
    started with --config finds its own certificates.
    """
    value = get_config(key)
    if not value:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(get_config_path()), str(value)))


def set_config(key, value):
    config = dict(load_config())
    config[key] = value
    save_config(config)
