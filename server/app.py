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
from shared.command_handler import ShutdownRequested, command_handler_async  # noqa: E402
from shared.network import check_port_free, get_local_ip, is_address_in_use, port_in_use_message  # noqa: E402
from shared.symbols import ERROR, WARNING  # noqa: E402
from handlers.server_handler import start_server_async  # noqa: E402
from handlers.store import (  # noqa: E402
    StoreError, close_store, count_clients, count_history, get_store_path, history_days, open_store, prune_history,
)

# how often old history is pruned while the server runs
PRUNE_SECONDS = 24 * 60 * 60
from handlers.web_handler import app, dashboard_warning  # noqa: E402
from handlers.discovery import discovery_port, start_discovery  # noqa: E402
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

def web_server():
    """The dashboard's uvicorn server; main() runs its serve() and stops it on shutdown."""
    uv_config = uvicorn.Config(
        app,
        host=get_config("WEB_HOST", "0.0.0.0"),
        port=get_config("WEB_PORT", 50001),
        # uvicorn logs every request, which would trample the command prompt
        log_level="warning",
        # the same certificate as the client listener, HTTPS only on this port
        **uvicorn_options(),
    )
    return uvicorn.Server(uv_config)

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
    removed = prune_history(history_days())
    line = f"Database {shown}, {count_clients()} clients known, {count_history()} history entries"
    if imported:
        line += f", {imported} imported from clients.json"
    if removed:
        line += f", {removed} older than {history_days()} days removed"
    print(line)

async def prune_daily():
    """Keep the history to HISTORY_DAYS while the server runs for weeks."""
    while True:
        await asyncio.sleep(PRUNE_SECONDS)
        prune_history(history_days())

def check_ports():
    """Fail with a readable line before anything starts.

    Before the database too: a second server started by mistake must not
    touch the first one's pyhome.db. uvicorn's own message would be a traceback.
    """
    for host, port, what in ((get_config("HOST"), get_config("PORT"), "clients"),
                             (get_config("WEB_HOST", "0.0.0.0"), get_config("WEB_PORT", 50001), "dashboard")):
        try:
            check_port_free(host, port)
        except OSError as e:
            if is_address_in_use(e):
                sys.exit(f"{ERROR} {port_in_use_message(port, what)}")
            raise

async def open_discovery():
    """Answer the launcher's Find servers. A port that cannot be used is a warning, not a stop."""
    port = discovery_port()
    if port is None:
        return None
    try:
        transport = await start_discovery(port)
    except OSError as e:
        reason = "already in use, probably by another pyhome server" if is_address_in_use(e) else str(e)
        print(f"{WARNING} {YELLOW}Discovery off, UDP port {port} {reason}{RESET}")
        return None
    print(f"Discovery answering on UDP port {port}, Find servers in the launcher sees this server")
    return transport

async def main():
    check_ports()
    open_database()
    server = await start_server_async()
    print_web_url()
    discovery = await open_discovery()

    web = web_server()
    web_task = asyncio.ensure_future(web.serve())

    # handlers
    try:
        await asyncio.gather(
            accept_clients(server),
            web_task,
            prune_daily(),
            command_handler_async(COMMAND_SOURCES)
        )
    except ShutdownRequested:
        # uvicorn's own way out: it finishes and stops, where a cancel would print a traceback
        web.should_exit = True
        await web_task
        server.close()
        # the client connections end here, while the store can still record when each was last seen
        others = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in others:
            task.cancel()
        await asyncio.gather(*others, return_exceptions=True)
        raise
    finally:
        if discovery is not None:
            discovery.close()
        # shutdown, Ctrl+C or a crash: the last connection folds the WAL file back into pyhome.db
        close_store()

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
    except ShutdownRequested as e:
        # the shutdown command, already said goodbye
        sys.exit(e.code)
    except SystemExit as e:
        # sys.exit(1) etc reaches here too (uvicorn uses it on a bind failure);
        # a clean shutdown (exit(0)) must close without a prompt
        if e.code is not None and e.code != 0:
            wait_for_enter()
        raise
    except Exception as e:
        print(f"Fatal error: {e}")
        wait_for_enter()
