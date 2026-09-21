import os
import sys
import asyncio

# the shared package sits next to this folder, so put the repo root on the path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
sys.path.insert(0, ROOT_DIR)

# config has to know which file is ours before anything reads it,
# --config picks another one so several instances can run from one folder
from shared import config  # noqa: E402
config.init(APP_DIR, config.config_file_from_argv(sys.argv))

from shared.config import get_config  # noqa: E402
from shared.console import wait_for_enter  # noqa: E402
from shared.command_handler import command_handler_async  # noqa: E402
from handlers.connection_handler import connect_to_server_async  # noqa: E402
from handlers.message_handler import receive_messages_async  # noqa: E402

NAME = get_config("NAME")
ID = get_config("ID")
VERSION = get_config("VERSION")

# commands are loaded from the shared folder first, then from our own
COMMAND_SOURCES = [
    (os.path.join(ROOT_DIR, "shared", "commands"), "shared.commands"),
    (os.path.join(APP_DIR, "handlers", "commands"), "handlers.commands"),
]

# init app, both commands only exist on windows
if os.name == "nt":
    os.system("color")
    os.system(f"title {NAME}#{ID} {VERSION}")

# run handlers in parallel
async def main():
    # handlers
    await asyncio.gather(
        connect_to_server_async(),
        receive_messages_async(),
        command_handler_async(COMMAND_SOURCES)
    )

# main
if __name__ == "__main__":
    try:
        try:
            import uvloop # type: ignore
            uvloop.install()
            print("Using uvloop asyncio")
        except ImportError:
            print("Using standard asyncio")
        asyncio.run(main())

    except KeyboardInterrupt:
        print(f"\n{NAME} is shutting down.")
    except SystemExit as e:
        # sys.exit(1) etc reaches here too (uvicorn uses it on a bind failure);
        # a clean shutdown (exit(0)) must close without a prompt
        if e.code is not None and e.code != 0:
            wait_for_enter()
        raise
    except Exception as e:
        print(f"Fatal error: {e}")
        wait_for_enter()
