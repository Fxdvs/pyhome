from shared.symbols import SUCCESS, ERROR
from handlers import store

command = ["data backup"]
description = "Writes a consistent copy of pyhome.db next to it, safe while the server runs"


async def function():
    try:
        path = store.backup()
    except Exception as e:
        print(f"{ERROR} Backup failed: {e}")
        return
    print(f"{SUCCESS} Backup written to {path}")
