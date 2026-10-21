import json

from shared.colors import GRAY, RESET
from shared.symbols import ERROR
from handlers import store
from handlers.client_handler import find_online_client

command = ["history"]
description = "Shows a client's last state changes: history <id or start of id> [count]"

# a page fits a console window
DEFAULT_COUNT = 10


def resolve(target):
    """The full id target names: any known client by its exact id, an online one by the start of it too."""
    if store.get_client(target) is not None:
        return target
    # an offline client has no prefix, LookupError says what is online
    return str(find_online_client(target)[1]["id"])


async def function(target=None, count=str(DEFAULT_COUNT)):
    if target is None:
        print(f"{ERROR} Usage: history <id or start of id> [count]")
        return
    try:
        limit = int(count)
        if limit < 1:
            raise ValueError
    except ValueError:
        print(f"{ERROR} count must be a whole number above 0, got '{count}'")
        return
    try:
        client_id = resolve(target)
    except LookupError as e:
        print(f"{ERROR} {e}")
        return

    entries = store.get_history(client_id, limit)
    if not entries:
        print(f"{GRAY}No history for {client_id}{RESET}")
        return
    print(f"History of {client_id}, newest first:")
    for entry in entries:
        when = store.local_time(entry["at"], "%d.%m. %H:%M:%S")
        state = json.dumps(entry["state"], ensure_ascii=False)
        print(f"  {when}  {entry['source']:<24} {state}")
