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


async def ask(prompt):
    """input() for an async command, off the event loop.

    input() blocks; called straight from a coroutine it would stop the whole
    server, clients and dashboard included, until someone answers.
    """
    return await asyncio.get_running_loop().run_in_executor(None, input, prompt)


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
