"""What the do and state commands share: reading key=value and printing results."""
import asyncio
import json
import math

from shared.colors import GREEN, RESET
from shared.symbols import ERROR, SUCCESS
from handlers.client_handler import COMMAND_TIMEOUT, send_command


def parse_value(text):
    """true/false, then int, then float, otherwise the text itself."""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        number = float(text)
    except ValueError:
        return text
    # inf and nan parse as floats but are not numbers anyone meant to send
    return number if math.isfinite(number) else text


def parse_params(tokens):
    """["level=40", "on=true"] -> {"level": 40, "on": True}. ValueError on a token without key=."""
    params = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep or not key:
            raise ValueError(f"expected key=value, got '{token}'")
        params[key] = parse_value(value)
    return params


async def run_and_print(client_id, action, params):
    try:
        result = await send_command(client_id, action, params)
    except LookupError as e:
        print(f"{ERROR} {e}")
        return
    except asyncio.TimeoutError:
        print(f"{ERROR} {client_id} did not answer within {COMMAND_TIMEOUT} s")
        return
    except OSError as e:
        print(f"{ERROR} {client_id}: {e}")
        return

    if result.get("ok"):
        state = json.dumps(result.get("state"), ensure_ascii=False)
        print(f"{SUCCESS} {GREEN}{client_id}{RESET} {action}: {state}")
    else:
        print(f"{ERROR} {client_id} {action} failed: {result.get('error')}")
