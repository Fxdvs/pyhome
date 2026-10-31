"""Real configs hold the token, so git must ignore them and keep only the examples."""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not os.path.exists(os.path.join(ROOT, ".git")),
    reason="needs git and a checkout",
)


def ignored(path):
    result = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT)
    return result.returncode == 0


@pytest.mark.parametrize("path", [
    "server/data/config.json",
    "client/data/config.json",
    "client/data/kuchyna-svetlo.json",
    "launcher/state.json",
])
def test_real_configs_ignored(path):
    assert ignored(path), path


@pytest.mark.parametrize("path", [
    "server/data/config.example.json",
    "client/data/config.example.json",
])
def test_examples_kept(path):
    assert not ignored(path), path
