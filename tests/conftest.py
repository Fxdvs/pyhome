"""Shared pytest setup.

Every test takes `tmp`, a fresh temporary folder as a str: the tests were
written for a runner of their own that passed exactly that, and a str reads
better than a Path in the os.path code they test. The working directory is
put back after each test, so a test may chdir into its folder.

Files named *_e2e.py start a real server and real clients as processes.
They are marked e2e, so `py -m pytest -m "not e2e"` runs the quick ones only.
"""
import os
import sys

import pytest

# store_db below imports the server's store, the test files put the same paths first anyway
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT_DIR, os.path.join(ROOT_DIR, "server")):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def tmp(tmp_path):
    cwd = os.getcwd()
    yield str(tmp_path)
    # windows cannot delete a folder that is the working directory
    os.chdir(cwd)


@pytest.fixture
def store_db(tmp):
    """A fresh pyhome.db in the test's folder, for tests that feed the server fake clients.

    The server writes every state it hears into the store, so a fake client
    has to be in it as well; register_client() does what a handshake would.
    """
    from handlers import store

    store.open_store(os.path.join(tmp, "pyhome.db"))
    yield store
    store.close_store()


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.name.endswith("_e2e.py"):
            item.add_marker(pytest.mark.e2e)
