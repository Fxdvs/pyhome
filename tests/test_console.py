"""shared/console.py: a prompt for a person at a terminal, plain lines for the launcher."""
import io
import os
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from shared import console  # noqa: E402


class Stream(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


@pytest.mark.parametrize("stdin, stdout, expected", [
    (True, True, True),
    (False, True, False),
    (True, False, False),
    (False, False, False),
])
def test_interactive_needs_both_ends_at_a_terminal(monkeypatch, stdin, stdout, expected):
    monkeypatch.setattr(sys, "stdin", Stream(stdin))
    monkeypatch.setattr(sys, "stdout", Stream(stdout))
    assert console.interactive() is expected


def test_interactive_without_streams(monkeypatch):
    # pythonw has no stdin or stdout at all
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "stdout", None)
    assert console.interactive() is False


def test_plain_line_without_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr(console, "interactive", lambda: False)
    console.print_message("Client kuchyna has connected")
    assert capsys.readouterr().out == "Client kuchyna has connected\n"


def test_prompt_redrawn_at_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr(console, "interactive", lambda: True)
    console.print_message("Client kuchyna has connected")
    out = capsys.readouterr().out
    assert out.startswith("\r") and out.endswith("Client kuchyna has connected\n" + console.PROMPT)


def test_prompt_only_at_a_terminal(monkeypatch):
    monkeypatch.setattr(console, "interactive", lambda: False)
    assert console.prompt() == "" and console.prompt(">") == ""
    monkeypatch.setattr(console, "interactive", lambda: True)
    assert console.prompt() == console.PROMPT and console.prompt(">") == ">"


def test_wait_for_enter_does_not_wait_without_a_terminal(monkeypatch):
    def no_input(*args):
        raise AssertionError("nobody is there to press Enter")
    monkeypatch.setattr(console, "interactive", lambda: False)
    monkeypatch.setattr("builtins.input", no_input)
    console.wait_for_enter()
