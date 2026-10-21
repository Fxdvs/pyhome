"""Loads the device named by DEVICE and runs its actions.

A device is a package in client/devices/<name>/ whose __init__.py declares
itself by module level names, the same way a command module does:

    device = "light"
    description = "Dimmable light"
    async def turn_on(**params): ...
    async def get_state(): return {...}
    actions = [turn_on, ...]          get_state is implied and always available

Modelled on shared/command_handler.py. Devices load from one folder only for
now, the signature takes the folder so that can grow later.
"""
import importlib
import inspect
import json
import os

GET_STATE = "get_state"

_device = None


def load_device(devices_dir, package, name):
    """Import <package>.<name> from devices_dir, or load nothing for an empty name.

    Raises ValueError when the device is missing or breaks the contract. A
    client configured as a light should stop, not quietly run as nothing.
    """
    global _device
    _device = None

    if not name:
        return None

    # a plain folder name, so DEVICE cannot reach into other modules
    if not isinstance(name, str) or not name.isidentifier() or not os.path.isdir(os.path.join(devices_dir, name)):
        raise ValueError(f"device '{name}' not found in {devices_dir}")

    module = importlib.import_module(f"{package}.{name}")

    actions = getattr(module, "actions", None)
    if not isinstance(actions, (list, tuple)) or not all(callable(f) for f in actions):
        raise ValueError(f"device '{name}' has no valid 'actions' list")
    if not callable(getattr(module, GET_STATE, None)):
        raise ValueError(f"device '{name}' has no {GET_STATE}()")

    _device = module
    return module


def get_device():
    """The loaded device module, or None."""
    return _device


def get_capabilities():
    """Action names, derived from the actions list so the two cannot drift."""
    if _device is None:
        return []
    return [f.__name__ for f in _device.actions]


async def _call(func, params):
    # actions are meant to be async, a plain def works as well
    result = func(**params)
    if inspect.isawaitable(result):
        result = await result
    return result


async def run_action(name, params):
    """Run one action and return what it returned. Raises LookupError when there is none."""
    if _device is None:
        raise LookupError("this client has no device")
    if name == GET_STATE:
        return await _call(_device.get_state, {})
    for func in _device.actions:
        if func.__name__ == name:
            return await _call(func, params)
    raise LookupError(f"unknown action '{name}'")


async def execute(name, params):
    """Run an action for a cmd message and build the result payload. Never raises.

    A failing action is an answer, not a broken connection, so every error
    becomes ok false plus the reason.
    """
    if not isinstance(params, dict):
        return {"ok": False, "error": "params must be an object"}
    try:
        await run_action(name, params)
        state = await _call(_device.get_state, {})
        # a state the device handed us but json cannot carry would otherwise
        # blow up inside send_message, deep in a task nobody awaits
        try:
            json.dumps(state)
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": f"device state is not JSON: {e}"}
        return {"ok": True, "state": state}
    except Exception as e:
        return {"ok": False, "error": str(e)}
