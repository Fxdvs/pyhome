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

from shared.colors import GREEN, RESET, YELLOW  # noqa: E402
from shared.config import get_config  # noqa: E402
from shared.console import wait_for_enter  # noqa: E402
from shared.command_handler import command_handler_async  # noqa: E402
from shared.network import get_local_ip  # noqa: E402
from shared.symbols import ERROR, WARNING  # noqa: E402
from handlers.server_handler import start_server_async  # noqa: E402
from handlers.store import StoreError, count_clients, get_store_path, open_store  # noqa: E402
from handlers.web_handler import app, dashboard_warning  # noqa: E402
from handlers.tls import ca_file, fingerprint, uvicorn_options  # noqa: E402

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
        # the same certificate as the client listener, HTTPS only on this port
        **uvicorn_options(),
    )
    server = uvicorn.Server(uv_config)
    await server.serve()

def print_web_url():
    host = get_config("WEB_HOST", "0.0.0.0")
    port = get_config("WEB_PORT", 50001)
    label = "Dashboard running on "
    scheme = "https" if uvicorn_options() else "http"

    print(f"{label}{GREEN}{scheme}://localhost:{port}{RESET}")

    # 0.0.0.0 means every interface, so show the address other devices can use
    if host == "0.0.0.0":
        print(f"{' ' * len(label)}{GREEN}{scheme}://{get_local_ip()}:{port}{RESET}")

    # what a phone shows when installing ca.crt, compare before trusting it
    ca = ca_file()
    if ca:
        print(f"{' ' * len(label)}ca.crt at /ca.crt, SHA-256 {fingerprint(ca)}")

    warning = dashboard_warning()
    if warning:
        print(f"{WARNING} {YELLOW}{warning}{RESET}")

# run handlers in parallel
def open_database():
    """Open pyhome.db before anything can connect. A database that cannot be used stops the server."""
    path = get_store_path()
    try:
        imported = open_store(path)
    except StoreError as e:
        sys.exit(f"{ERROR} {e}")
    shown = os.path.relpath(path, ROOT_DIR) if path.startswith(ROOT_DIR) else path
    line = f"Database {shown}, {count_clients()} clients known"
    if imported:
        line += f", {imported} imported from clients.json"
    print(line)

async def main():
    open_database()
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
    except SystemExit as e:
        # sys.exit(1) etc reaches here too (uvicorn uses it on a bind failure);
        # a clean shutdown (exit(0)) must close without a prompt
        if e.code is not None and e.code != 0:
            wait_for_enter()
        raise
    except Exception as e:
        print(f"Fatal error: {e}")
        wait_for_enter()
