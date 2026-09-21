"""A heating thermostat. Simulated, the room stays at ROOM_TEMPERATURE."""
from shared.console import print_message

device = "thermostat"
description = "Heating thermostat"

ROOM_TEMPERATURE = 20.5
MIN_TARGET = 5
MAX_TARGET = 30

_state = {"on": False, "target": 21.0}


async def turn_on(**params):
    _state["on"] = True
    print_message(f"Thermostat on, target {_state['target']} °C")


async def turn_off(**params):
    _state["on"] = False
    print_message("Thermostat off")


async def set_target(temperature=21.0, **params):
    # bool is an int in python, so true would otherwise mean 1 °C
    valid = isinstance(temperature, (int, float)) and not isinstance(temperature, bool)
    if not valid or not MIN_TARGET <= temperature <= MAX_TARGET:
        raise ValueError(f"temperature must be a number from {MIN_TARGET} to {MAX_TARGET}")
    _state["target"] = float(temperature)
    print_message(f"Thermostat target {_state['target']} °C")


async def get_state():
    heating = _state["on"] and ROOM_TEMPERATURE < _state["target"]
    return {**_state, "current": ROOM_TEMPERATURE, "heating": heating}


# what this device accepts, get_state is implied and always available
actions = [turn_on, turn_off, set_target]
