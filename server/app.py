import os
import sys
import asyncio
import uvicorn

# the shared package sits next to this folder, so put the repo root on the path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
sys.path.insert(0, ROOT_DIR)

# config has to know which file is ours before anything reads it,
# --config picks another one so several instances can run from one folder
from shared import config  # noqa: E402
config.init(APP_DIR, config.config_file_from_argv(sys.argv))

from shared.colors import GREEN, RESET  # noqa: E402
from shared.config import get_config  # noqa: E402
from shared.command_handler import command_handler_async  # noqa: E402
from shared.network import get_local_ip  # noqa: E402
from handlers.server_handler import start_server_async  # noqa: E402
from handlers.web_handler import app  # noqa: E402

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

# handle client connections
async def accept_clients(server):
    async with server:
        await server.serve_forever()

async def start_web():
    uv_config = uvicorn.Config(
        app,
        host=get_config("WEB_HOST", "0.0.0.0"),
        port=get_config("WEB_PORT", 50001),
        # uvicorn logs every request, which would trample the command prompt
        log_level="warning",
    )
    server = uvicorn.Server(uv_config)
    await server.serve()

def print_web_url():
    host = get_config("WEB_HOST", "0.0.0.0")
    port = get_config("WEB_PORT", 50001)
    label = "Dashboard running on "

    print(f"{label}{GREEN}http://localhost:{port}{RESET}")

    # 0.0.0.0 means every interface, so show the address other devices can use
    if host == "0.0.0.0":
        print(f"{' ' * len(label)}{GREEN}http://{get_local_ip()}:{port}{RESET}")

# run handlers in parallel
async def main():
    server = await start_server_async()
    print_web_url()

    # handlers
    await asyncio.gather(
        accept_clients(server),
        start_web(),
        command_handler_async(COMMAND_SOURCES)
    )

# main
if __name__ == "__main__":
    try:
         # try to use uvloop if os supports it
        try:
            import uvloop # type: ignore
            uvloop.install()
            print("Using uvloop asyncio")
        except ImportError:
            print("Using standard asyncio")
        asyncio.run(main())

    except KeyboardInterrupt:
        print(f"\n{NAME} is turned off.")
    except Exception as e:
        print(f"Fatal error: {e}")
        # the launcher starts us without a batch file ending in pause,
        # so without this the window closes before the error can be read
        try:
            input("Press Enter to close.")
        except (EOFError, KeyboardInterrupt):
            pass
