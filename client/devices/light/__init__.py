"""A dimmable light. Simulated, it prints what a real one would do."""
from shared.console import print_message

device = "light"
description = "Dimmable light"

_state = {"on": False, "brightness": 100}


async def turn_on(**params):
    _state["on"] = True
    print_message(f"Light on, brightness {_state['brightness']}")


async def turn_off(**params):
    _state["on"] = False
    print_message("Light off")


async def set_brightness(level=100, **params):
    # bool is an int in python, so true would otherwise mean brightness 1
    if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 100:
        raise ValueError("level must be a whole number from 0 to 100")
    _state["brightness"] = level
    print_message(f"Light brightness {level}")


async def get_state():
    return dict(_state)


# what this device accepts, get_state is implied and always available
actions = [turn_on, turn_off, set_brightness]
