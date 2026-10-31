"""launcher.pyw: the Tkinter window loads and uses launcher/core.py."""
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader

import pytest

# the window is tkinter; a python without tkinter cannot even import it
pytest.importorskip("tkinter")

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


def test_window_uses_the_core():
    from launcher import core
    window = load_window()
    assert window.list_client_configs is core.list_client_configs
    assert window.App is core.App
    assert window.ensure_default_configs is core.ensure_default_configs
