"""Printing that does not eat the command prompt.

Both sides read commands at a "> " prompt while messages arrive in the
background. Printing straight to stdout would leave the half typed prompt
in the middle of the output, so every message goes through here.

Started by the launcher, an app has pipes instead of a terminal. Nobody
sees a prompt there, so none is drawn and every message is a plain line.
"""
import asyncio
import re
import sys
import threading

from shared.colors import GRAY, RESET

print_lock = threading.Lock()

PROMPT = "> "

_ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def interactive():
    """True when a person types at a terminal: stdin and stdout are both one."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        # no stdin or stdout at all (pythonw), or a closed one
        return False


def prompt(text=PROMPT):
    """text where a prompt is drawn, nothing when nobody is at a terminal."""
    return text if interactive() else ""


def visible_len(text):
    """Length on screen, ignoring color codes."""
    return len(_ANSI.sub("", str(text)))


def print_message(message: str):
    if not interactive():
        with print_lock:
            print(message, flush=True)
        return
    with print_lock:
        # wipe the prompt line
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

        print(message)

        # draw the prompt again
        sys.stdout.write(PROMPT)
        sys.stdout.flush()


async def read_line(text=""):
    """input() off the event loop, in a thread the app does not wait for when it exits.

    input() blocks; called straight from a coroutine it would stop the whole
    server, clients and dashboard included. In the loop's own thread pool it
    would hold the exit instead: Python joins those threads, and one waiting
    for a line that never comes (docker stop, the launcher's Stop) never ends.
    """
    loop = asyncio.get_running_loop()
    answer = loop.create_future()

    def deliver(setter, value):
        if not answer.done():
            setter(value)

    def read():
        try:
            value, setter = input(text), answer.set_result
        except BaseException as e:  # EOFError, KeyboardInterrupt, a closed stdin
            value, setter = e, answer.set_exception
        try:
            loop.call_soon_threadsafe(deliver, setter, value)
        except RuntimeError:
            # the loop is gone, the app is ending
            pass

    threading.Thread(target=read, name="console input", daemon=True).start()
    return await answer


async def ask(prompt):
    """input() for an async command, off the event loop."""
    return await read_line(prompt)


def wait_for_enter():
    """Blocks on Enter so the message above it can be read before the console closes.

    The launcher starts apps without a batch file ending in pause, so
    without this the window closes the instant the app ends. Without a
    terminal nobody would press it, and the launcher keeps the output anyway.
    """
    if not interactive():
        return
    try:
        input("Press Enter to close.")
    except (EOFError, KeyboardInterrupt):
        pass


def print_info(title, rows, gap=50, margin=" " * 5):
    """A titled block of label/value rows, values lined up at column `gap`."""
    print("\n" + margin + title)
    print(margin + f"{GRAY}{'─' * gap}{RESET}")

    for label, value in rows:
        pad = max(1, gap - visible_len(value) - len(label))
        print(margin + label + " " * pad + str(value))

    print()
