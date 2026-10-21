"""Shared pytest setup.

Every test takes `tmp`, a fresh temporary folder as a str: the tests were
written for a runner of their own that passed exactly that, and a str reads
better than a Path in the os.path code they test. The working directory is
put back after each test, so a test may chdir into its folder.

Files named *_e2e.py start a real server and real clients as processes.
They are marked e2e, so `py -m pytest -m "not e2e"` runs the quick ones only.
"""
import os

import pytest


@pytest.fixture
def tmp(tmp_path):
    cwd = os.getcwd()
    yield str(tmp_path)
    # windows cannot delete a folder that is the working directory
    os.chdir(cwd)


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.name.endswith("_e2e.py"):
            item.add_marker(pytest.mark.e2e)
