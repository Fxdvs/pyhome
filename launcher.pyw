"""Starts the server and any number of clients, each in its own console.

Clients are every config file in client/data, so a config file is one instance
with its own id. The launcher holds the processes it started, shows whether
they are still running and can stop them. What it does lives in launcher/core.py.
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# the shared and launcher packages sit next to this file
sys.path.insert(0, ROOT_DIR)

from launcher.core import (  # noqa: E402
    CLIENT_DATA_DIR, CLIENT_DIR, POLL_MS, SERVER_CONFIG, SERVER_DIR,
    COLOR_EXITED, COLOR_RUNNING, COLOR_STOPPED, App, ensure_default_configs, head_start_ms, list_client_configs,
)


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
                if entry["note"]:
                    detail += f"  ! {entry['note']}"
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
        # rows hold the server first (see refresh), so this is always its row
        server_app, server_var, _ = self.rows[0]
        client_rows = self.rows[1:]

        server_started = server_var.get() and self.start_app(server_app)

        delay = head_start_ms(server_started)
        if delay:
            self.root.after(delay, lambda: self.start_rows(client_rows))
        else:
            self.start_rows(client_rows)

        self.update_status()

    def start_app(self, app):
        """Starts app, reporting a failure to start instead of raising."""
        try:
            return app.start()
        except OSError as e:
            messagebox.showerror("Smart home launcher", f"Could not start {app.label}:\n{e}")
            return False

    def start_rows(self, rows):
        for app, var, _ in rows:
            if var.get():
                self.start_app(app)
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
    # a fresh checkout has only the example configs, which are in git
    ensure_default_configs()
    root = tk.Tk()
    LauncherWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
