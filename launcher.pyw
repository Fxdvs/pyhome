"""Starts the server and any number of clients, each in its own console.

Clients are every config file in client/data, so a config file is one instance
with its own id. The launcher holds the processes it started, shows whether
they are still running and can stop them.
"""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(ROOT_DIR, "server")
CLIENT_DIR = os.path.join(ROOT_DIR, "client")
SERVER_CONFIG = os.path.join(SERVER_DIR, "data", "config.json")
CLIENT_DATA_DIR = os.path.join(CLIENT_DIR, "data")

# only exists on windows, elsewhere the apps share the launcher's terminal
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

# how often the status column is refreshed, in milliseconds
POLL_MS = 1000

COLOR_RUNNING = "#2e7d32"
COLOR_STOPPED = "#757575"
COLOR_EXITED = "#c62828"


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


class LauncherWindow:
    """Server row, one row per client config, and Run, Stop all, Refresh."""

    def __init__(self, root):
        self.root = root
        root.title("Smart home launcher")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # keyed by config path, so a refresh keeps what is running and ticked
        self.apps = {}
        self.checked = {}
        # (App, BooleanVar, status Label) for what is on screen, server first
        self.rows = []

        self.body = tk.Frame(root, padx=10, pady=10)
        self.body.pack(fill="both", expand=True)

        buttons = tk.Frame(root, padx=10)
        buttons.pack(fill="x", pady=(0, 10))
        tk.Button(buttons, text="Run", width=10, command=self.run).pack(side="left")
        tk.Button(buttons, text="Stop all", width=10, command=self.stop_all).pack(side="left", padx=5)
        tk.Button(buttons, text="Refresh", width=10, command=self.refresh).pack(side="left")

        self.refresh()
        self.poll()

    def get_app(self, label, app_dir, config_path):
        if config_path not in self.apps:
            self.apps[config_path] = App(label, app_dir, config_path)
        return self.apps[config_path]

    def get_checked(self, config_path, enabled):
        if config_path not in self.checked:
            self.checked[config_path] = tk.BooleanVar(value=enabled)
        return self.checked[config_path]

    def refresh(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        self.rows = []

        tk.Label(self.body, text="Server", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        server = self.get_app("server", SERVER_DIR, SERVER_CONFIG)
        self.add_row(1, server, "server/data/config.json", "", True)

        tk.Label(self.body, text="Clients", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        row = 3
        for entry in list_client_configs(CLIENT_DATA_DIR):
            app = self.get_app(entry["file"], CLIENT_DIR, entry["path"])
            if entry["error"]:
                detail = entry["error"]
            else:
                detail = f"{entry['name'] or ''}  {entry['device'] or '(no device)'}"
            self.add_row(row, app, entry["file"], detail, entry["error"] is None)
            row += 1

        self.update_status()

    def add_row(self, row, app, text, detail, enabled):
        var = self.get_checked(app.config_path, enabled)
        check = tk.Checkbutton(self.body, text=text, variable=var, anchor="w")
        if not enabled:
            var.set(False)
            check.config(state="disabled")
        check.grid(row=row, column=0, sticky="w")
        tk.Label(self.body, text=detail, anchor="w").grid(row=row, column=1, sticky="w", padx=10)
        status = tk.Label(self.body, width=12, anchor="w")
        status.grid(row=row, column=2, sticky="w")
        tk.Button(self.body, text="Stop", command=lambda: self.stop(app)).grid(row=row, column=3, padx=(5, 0))
        self.rows.append((app, var, status))

    def run(self):
        # rows hold the server first, so the clients find it on their first try
        for app, var, _ in self.rows:
            if not var.get():
                continue
            try:
                app.start()
            except OSError as e:
                messagebox.showerror("Smart home launcher", f"Could not start {app.label}:\n{e}")
        self.update_status()

    def stop(self, app):
        app.stop()
        self.update_status()

    def stop_all(self):
        # every app ever started, also those whose config has since disappeared
        for app in self.apps.values():
            app.stop()
        self.update_status()

    def update_status(self):
        for app, _, label in self.rows:
            status = app.status()
            if status == "running":
                color = COLOR_RUNNING
            elif status == "stopped":
                color = COLOR_STOPPED
            else:
                color = COLOR_EXITED
            label.config(text=status, fg=color)

    def poll(self):
        self.update_status()
        self.root.after(POLL_MS, self.poll)

    def on_close(self):
        running = [app for app in self.apps.values() if app.is_running()]
        if running:
            answer = messagebox.askyesnocancel(
                "Smart home launcher",
                f"{len(running)} app(s) still running. Stop them?\n\n"
                "Yes stops them, No leaves them running.",
            )
            if answer is None:
                return
            if answer:
                self.stop_all()
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
