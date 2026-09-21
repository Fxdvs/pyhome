"""Starts the server and any number of clients, each in its own console.

Clients are every config file in client/data, so a config file is one instance
with its own id. The launcher holds the processes it started, shows whether
they are still running and can stop them.
"""
import json
import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(ROOT_DIR, "server")
CLIENT_DIR = os.path.join(ROOT_DIR, "client")
SERVER_CONFIG = os.path.join(SERVER_DIR, "data", "config.json")
CLIENT_DATA_DIR = os.path.join(CLIENT_DIR, "data")

# only exists on windows, elsewhere the apps share the launcher's terminal
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def python_executable(executable=sys.executable):
    """The console python next to executable.

    Double clicking a .pyw runs pythonw.exe, which has no console. The apps
    would inherit it and their windows would never open.
    """
    folder, name = os.path.split(executable)
    if name.lower() == "pythonw.exe":
        return os.path.join(folder, "python.exe")
    return executable


def list_client_configs(data_dir):
    """One entry per *.json in data_dir, sorted by file name."""
    if not os.path.isdir(data_dir):
        return []

    entries = []
    for file in sorted(os.listdir(data_dir)):
        if not file.endswith(".json"):
            continue

        path = os.path.join(data_dir, file)
        entry = {"file": file, "path": path, "name": None, "device": None, "error": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry["name"] = data.get("NAME")
            entry["device"] = data.get("DEVICE") or None
        except (OSError, ValueError, AttributeError):
            # AttributeError: valid JSON that is not an object has no .get
            entry["error"] = "invalid JSON"
        entries.append(entry)
    return entries


def build_command(config_path):
    return [python_executable(), "app.py", "--config", config_path]


class App:
    """One server or client process that the launcher started, or can start."""

    def __init__(self, label, app_dir, config_path, creationflags=NEW_CONSOLE):
        self.label = label
        self.app_dir = app_dir
        self.config_path = config_path
        self.creationflags = creationflags
        self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def status(self):
        if self.process is None:
            return "stopped"
        code = self.process.poll()
        if code is None:
            return "running"
        return f"exited ({code})"

    def start(self):
        """Returns False when it was already running."""
        if self.is_running():
            return False
        self.process = subprocess.Popen(
            build_command(self.config_path),
            cwd=self.app_dir,
            creationflags=self.creationflags,
        )
        return True

    def stop(self):
        # terminate, the app's own shutdown needs someone typing in its console
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process = None
