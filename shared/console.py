"""Printing that does not eat the command prompt.

Both sides read commands at a "> " prompt while messages arrive in the
background. Printing straight to stdout would leave the half typed prompt
in the middle of the output, so every message goes through here.
"""
import re
import sys
import threading

from shared.colors import GRAY, RESET

print_lock = threading.Lock()

PROMPT = "> "

_ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def visible_len(text):
    """Length on screen, ignoring color codes."""
    return len(_ANSI.sub("", str(text)))


def print_message(message: str):
    with print_lock:
        # wipe the prompt line
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

        print(message)

        # draw the prompt again
        sys.stdout.write(PROMPT)
        sys.stdout.flush()


def wait_for_enter():
    """Blocks on Enter so the message above it can be read before the console closes.

    The launcher starts apps without a batch file ending in pause, so
    without this the window closes the instant the app ends.
    """
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
