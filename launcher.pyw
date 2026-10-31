"""Opens the launcher: the server and every client in one window, each with its output and command line.

Double click it on Windows. The window is launcher/web/index.html in the
system web view (pywebview), everything it does is launcher/api.py.
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# the shared and launcher packages sit next to this file
sys.path.insert(0, ROOT_DIR)

from launcher.api import Api  # noqa: E402
from launcher.core import ensure_default_configs  # noqa: E402

INDEX = os.path.join(ROOT_DIR, "launcher", "web", "index.html")
TITLE = "pyhome"
INSTALL = "py -m pip install -r requirements-launcher.txt"


def tell(message):
    """Show message without a console: pythonw has none, so a print would vanish."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, TITLE, 0x10)
    else:
        print(message, file=sys.stderr)


def main():
    try:
        import webview
    except ImportError:
        tell(f"The launcher needs pywebview. Install it with:\n\n{INSTALL}")
        sys.exit(1)

    # a fresh checkout has only the example configs, which are in git
    ensure_default_configs()
    api = Api()
    window = webview.create_window(
        TITLE, INDEX, js_api=api,
        width=1180, height=760, min_size=(760, 520),
        # the page's own background, so the window does not flash white while it loads
        background_color="#07080d",
    )
    api._attach(window)
    window.events.closing += lambda *args: api._on_closing()
    webview.start()
    # closed some other way than quit (the system ending the session): leave nothing running
    api.stop_all(wait=True)
    # A call from the page still in flight when the window closed waits for a page that is
    # gone, on a thread that would keep this process alive, invisible, forever.
    os._exit(0)


if __name__ == "__main__":
    main()
