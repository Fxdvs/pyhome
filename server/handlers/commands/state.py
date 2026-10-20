from shared.symbols import ERROR
from handlers.client_handler import GET_STATE
from handlers.devices import run_and_print

command = ["state"]
description = "Asks a client for its device state: state <id>"


async def function(client_id=None):
    if client_id is None:
        print(f"{ERROR} Usage: state <client id>")
        return
    await run_and_print(client_id, GET_STATE, {})
