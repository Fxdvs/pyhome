"""launcher.pyw without the window: listing configs and handling processes."""
import importlib.util
import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)

from helpers import run_tests  # noqa: E402

# a .pyw is not importable by name, so load it from its path
_loader = SourceFileLoader("launcher", os.path.join(ROOT_DIR, "launcher.pyw"))
launcher = importlib.util.module_from_spec(importlib.util.spec_from_loader("launcher", _loader))
_loader.exec_module(launcher)

# no console windows popping up while the tests run
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_lists_client_configs(tmp):
    write(os.path.join(tmp, "b.json"), json.dumps({"NAME": "Plain"}))
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "Kitchen", "DEVICE": "light"}))
    write(os.path.join(tmp, "c.json"), "{not json")
    write(os.path.join(tmp, "notes.txt"), "ignored")

    entries = launcher.list_client_configs(tmp)

    assert [e["file"] for e in entries] == ["a.json", "b.json", "c.json"], entries
    a, b, c = entries
    assert a == {"file": "a.json", "path": os.path.join(tmp, "a.json"),
                 "name": "Kitchen", "device": "light", "error": None}, a
    assert b["name"] == "Plain" and b["device"] is None and b["error"] is None, b
    assert c["error"] == "invalid JSON" and c["name"] is None, c


def test_empty_device_counts_as_none(tmp):
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "A", "DEVICE": ""}))
    assert launcher.list_client_configs(tmp)[0]["device"] is None


def test_json_that_is_not_an_object_is_invalid(tmp):
    write(os.path.join(tmp, "a.json"), "[1, 2]")
    assert launcher.list_client_configs(tmp)[0]["error"] == "invalid JSON"


def test_missing_data_dir_lists_nothing(tmp):
    assert launcher.list_client_configs(os.path.join(tmp, "nope")) == []


def test_pythonw_becomes_python(tmp):
    folder = os.path.join("C:\\", "Python313")
    assert launcher.python_executable(os.path.join(folder, "pythonw.exe")) == os.path.join(folder, "python.exe")
    assert launcher.python_executable(os.path.join(folder, "PythonW.EXE")) == os.path.join(folder, "python.exe")
    assert launcher.python_executable(os.path.join(folder, "python.exe")) == os.path.join(folder, "python.exe")


def test_build_command(tmp):
    command = launcher.build_command("C:\\cfg\\kitchen.json")
    assert command[1:] == ["app.py", "--config", "C:\\cfg\\kitchen.json"], command
    assert command[0] == launcher.python_executable()


def make_fake_app(tmp, body):
    """An app.py in tmp that records how it was started, then runs body."""
    write(os.path.join(tmp, "app.py"),
          "import json, os, sys, time\n"
          "with open('started.json', 'w') as f:\n"
          "    json.dump({'argv': sys.argv[1:], 'cwd': os.getcwd()}, f)\n"
          + body)
    config_path = os.path.join(tmp, "config.json")
    write(config_path, "{}")
    return launcher.App("fake", tmp, config_path, creationflags=NO_WINDOW)


def test_app_start_passes_config_and_cwd(tmp):
    app = make_fake_app(tmp, "sys.exit(3)\n")
    assert app.status() == "stopped"
    assert app.start() is True
    app.process.wait(timeout=10)

    assert app.status() == "exited (3)", app.status()
    with open(os.path.join(tmp, "started.json"), encoding="utf-8") as f:
        started = json.load(f)
    assert started["argv"] == ["--config", app.config_path], started
    assert os.path.samefile(started["cwd"], tmp), started


def test_app_stop_ends_a_running_process(tmp):
    app = make_fake_app(tmp, "time.sleep(60)\n")
    assert app.start() is True
    assert app.is_running() and app.status() == "running"
    assert app.start() is False, "starting twice must not start a second process"

    process = app.process
    app.stop()
    assert process.poll() is not None, "the process should be gone"
    assert app.process is None and app.status() == "stopped"


def test_stop_on_a_stopped_app_does_nothing(tmp):
    app = make_fake_app(tmp, "")
    app.stop()
    assert app.status() == "stopped"


def test_real_paths(tmp):
    assert os.path.isfile(os.path.join(launcher.SERVER_DIR, "app.py"))
    assert os.path.isfile(os.path.join(launcher.CLIENT_DIR, "app.py"))
    assert launcher.SERVER_CONFIG == os.path.join(launcher.SERVER_DIR, "data", "config.json")
    assert launcher.CLIENT_DATA_DIR == os.path.join(launcher.CLIENT_DIR, "data")


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
