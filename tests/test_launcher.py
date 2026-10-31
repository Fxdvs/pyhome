"""launcher.pyw: the window opens the page with the api; pywebview itself is not started here."""
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, ROOT_DIR)


def load_window():
    # a .pyw is not importable by name; not under the name "launcher" either,
    # which is the package it imports from
    loader = SourceFileLoader("launcher_window", os.path.join(ROOT_DIR, "launcher.pyw"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("launcher_window", loader))
    loader.exec_module(module)
    return module


def test_loads_without_pywebview():
    # pywebview is imported in main(), so a missing one is a message, not a traceback on load
    window = load_window()
    assert os.path.isfile(window.INDEX)
    assert "requirements-launcher.txt" in window.INSTALL


def test_the_tkinter_window_is_gone():
    with open(os.path.join(ROOT_DIR, "launcher.pyw"), encoding="utf-8") as f:
        assert "tkinter" not in f.read()
