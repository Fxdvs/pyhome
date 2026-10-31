"""The methods the launcher's page calls, through pywebview's window.pywebview.api.

Every answer is plain JSON. Apps are addressed by key: "server", or a
client's config file name ("kuchyna-svetlo.json"). Nothing here knows about
pywebview except attach() and on_closing(), so all of it is tested without
a window.

pywebview exposes every public attribute of this object to the page, so
everything that is not a method for the page starts with an underscore.
"""
import os
import threading
import time

from launcher import core
from launcher.runner import Runner

SERVER = "server"


class Api:
    def __init__(self, root=core.ROOT_DIR, head_start=core.SERVER_HEAD_START_MS / 1000):
        self._server_dir = os.path.join(root, "server")
        self._client_dir = os.path.join(root, "client")
        self._server_config = os.path.join(self._server_dir, "data", "config.json")
        self._client_data = os.path.join(self._client_dir, "data")
        self._devices_dir = os.path.join(self._client_dir, "devices")
        self._certs_dir = os.path.join(self._server_dir, "data", "certs")
        self._make_certs = os.path.join(self._server_dir, "make_certs.py")
        self._state_path = os.path.join(root, "launcher", "state.json")
        self._head_start = head_start
        self._lock = threading.RLock()
        self._runners = {}
        self._window = None
        self._quitting = False
        self._state = core.load_state(self._state_path)

    # apps

    def _client_entries(self):
        return core.list_client_configs(self._client_data)

    def _config_path(self, key):
        if key == SERVER:
            return self._server_config
        path = os.path.join(self._client_data, os.path.basename(str(key)))
        return path if os.path.isfile(path) else None

    def _runner(self, key):
        """The Runner for key, made on first use. None when key is not an app."""
        with self._lock:
            if key not in self._runners:
                path = self._config_path(key)
                if path is None:
                    return None
                app_dir = self._server_dir if key == SERVER else self._client_dir
                self._runners[key] = Runner(core.build_command(path), cwd=app_dir)
            return self._runners[key]

    def _remembered(self):
        """The state, or on first start: everything that can run is ticked, the server selected."""
        if self._state is None:
            keys = [SERVER] + [e["file"] for e in self._client_entries() if not e["error"]]
            self._state = {"checked": keys, "selected": SERVER}
        return self._state

    def _save_state(self):
        try:
            core.save_state(self._state_path, self._state)
        except OSError:
            # only a convenience, never worth an error in the page
            pass

    def _read(self, path):
        try:
            return core.read_config(path)
        except (OSError, ValueError):
            return {}

    def _status(self, key):
        runner = self._runners.get(key)
        return runner.status() if runner else {"state": "stopped", "code": None, "uptime": None}

    def apps(self):
        """Everything the sidebar and the header show, the server first."""
        with self._lock:
            state = self._remembered()
            server = self._read(self._server_config)
            entries = [{
                "key": SERVER,
                "kind": "server",
                "name": server.get("NAME") or "Server",
                "id": server.get("ID") or "",
                "sub": "server/data/config.json",
                "meta": f"port {server.get('PORT', '?')} · dashboard {server.get('WEB_PORT', '?')}",
                "chips": ["TLS" if server.get("TLS_CERT") else "bez TLS",
                          "token" if server.get("TOKEN") else "bez tokenu"],
                "error": None,
                "note": None,
            }]
            for entry in self._client_entries():
                data = self._read(entry["path"])
                device = entry["device"] or "bez zariadenia"
                entries.append({
                    "key": entry["file"],
                    "kind": "client",
                    "name": entry["name"] or entry["file"],
                    "id": entry["id"] or "",
                    "sub": f"{device} · {entry['file']}",
                    "meta": f"→ {data.get('HOST', '?')}:{data.get('PORT', '?')}",
                    "chips": [device, "TLS" if data.get("TLS_CA") else "bez TLS"],
                    "error": entry["error"],
                    "note": entry["note"],
                })
            keys = {e["key"] for e in entries}
            for entry in entries:
                entry["checked"] = entry["key"] in state["checked"]
                entry["status"] = self._status(entry["key"])
            selected = state["selected"] if state["selected"] in keys else SERVER
            return {"apps": entries, "selected": selected}

    def select(self, key):
        with self._lock:
            self._remembered()["selected"] = key
            self._save_state()
        return True

    def check(self, key, checked):
        with self._lock:
            keys = [k for k in self._remembered()["checked"] if k != key]
            if checked:
                keys.append(key)
            self._state["checked"] = keys
            self._save_state()
        return True

    # running

    def start(self, key):
        runner = self._runner(key)
        return bool(runner and runner.start())

    def stop(self, key):
        """Stops in the background: Stop may take seconds, the page polls the state meanwhile."""
        runner = self._runners.get(key)
        if runner is None or not runner.is_running():
            return False
        threading.Thread(target=runner.stop, daemon=True).start()
        return True

    def restart(self, key):
        def again():
            runner = self._runner(key)
            if runner:
                runner.stop()
                runner.start()
        threading.Thread(target=again, daemon=True).start()
        return True

    def run_checked(self):
        """Start every ticked app that is not running, the server first with a head start."""
        apps = [a for a in self.apps()["apps"] if a["checked"] and not a["error"]
                and a["status"]["state"] != "running"]

        def run():
            for app in apps:
                started = self.start(app["key"])
                if app["key"] == SERVER and started and len(apps) > 1:
                    # the clients' first connection must not land before the server listens
                    time.sleep(self._head_start)
        threading.Thread(target=run, daemon=True).start()
        return [a["key"] for a in apps]

    def running(self):
        """Keys of the apps that run now."""
        with self._lock:
            return [key for key, runner in self._runners.items() if runner.is_running()]

    def stop_all(self, wait=False):
        """Stop every running app, all at once. With wait, return when they all ended."""
        with self._lock:
            runners = [r for r in self._runners.values() if r.is_running()]
        threads = [threading.Thread(target=r.stop, daemon=True) for r in runners]
        for thread in threads:
            thread.start()
        if wait:
            for thread in threads:
                thread.join()
        return len(runners)

    def output(self, key, since=0):
        runner = self._runners.get(key)
        if runner is None:
            return {"lines": [], "last": 0, "status": self._status(key)}
        answer = runner.output(int(since or 0))
        answer["status"] = runner.status()
        return answer

    def send(self, key, line):
        runner = self._runners.get(key)
        return bool(runner and runner.send(str(line)))

    # the client form

    def devices(self):
        return core.list_devices(self._devices_dir)

    def suggest_id(self, name):
        return core.id_from_name(name)

    def _server_here(self):
        """What a client form can take from the server in this checkout."""
        server = self._read(self._server_config)
        return {
            "port": server.get("PORT", 50000),
            "token": bool(server.get("TOKEN")),
            "tls": os.path.isfile(os.path.join(self._certs_dir, "ca.crt")),
        }

    def client_form(self, key=None):
        """The values a new or edited client's sheet opens with, and its choices."""
        here = self._server_here()
        form = {"key": key, "devices": self.devices(), "server": here}
        if key is None:
            devices = form["devices"]
            form["fields"] = {
                "name": "", "id": "", "device": devices[0] if devices else "",
                "host": "127.0.0.1", "port": str(here["port"]),
                "use_server_token": here["token"], "token": "", "tls": here["tls"],
            }
            return form
        path = self._config_path(key)
        data = self._read(path) if path else {}
        form["fields"] = {
            "name": data.get("NAME", ""), "id": data.get("ID", ""), "device": data.get("DEVICE") or "",
            "host": data.get("HOST", ""), "port": str(data.get("PORT", "")),
            "use_server_token": False, "token": data.get("TOKEN", ""), "tls": bool(data.get("TLS_CA")),
        }
        return form

    def save_client(self, fields, key=None):
        """{"ok", "errors" per field, "key" of the saved config, "running" when it runs with the old settings}."""
        fields = dict(fields or {})
        if fields.get("use_server_token"):
            fields["token"] = core.server_token(self._server_config)
        original = self._config_path(key) if key else None
        try:
            path = core.save_client(fields, data_dir=self._client_data, devices=self.devices(),
                                    ca_source=os.path.join(self._certs_dir, "ca.crt"), original_path=original)
        except core.ConfigError as e:
            return {"ok": False, "errors": e.errors}
        new_key = os.path.basename(path)
        with self._lock:
            if key and key != new_key and key in self._runners:
                # the running app keeps its output under the new name, and starts from the new file next time
                runner = self._runners.pop(key)
                runner.command = core.build_command(path)
                self._runners[new_key] = runner
            state = self._remembered()
            state["checked"] = [new_key if k == key else k for k in state["checked"]]
            if new_key not in state["checked"]:
                state["checked"].append(new_key)
            state["selected"] = new_key
            self._save_state()
        running = bool(key) and self._status(new_key)["state"] == "running"
        return {"ok": True, "errors": {}, "key": new_key, "running": running}

    # the server's settings

    def server_form(self):
        data = self._read(self._server_config)
        return {"fields": {
            "name": data.get("NAME", ""), "port": str(data.get("PORT", 50000)),
            "web_port": str(data.get("WEB_PORT", 50001)), "token": data.get("TOKEN", ""),
            "history_days": str(data.get("HISTORY_DAYS", 90)),
        }, "tls": bool(data.get("TLS_CERT"))}

    def save_server(self, fields):
        try:
            core.save_server(dict(fields or {}), self._server_config)
        except core.ConfigError as e:
            return {"ok": False, "errors": e.errors}
        return {"ok": True, "errors": {}, "running": self._status(SERVER)["state"] == "running"}

    def generate_token(self):
        return core.generate_token()

    def make_certificates(self, hosts=""):
        """hosts: names or addresses separated by spaces or commas, besides the ones make_certs adds itself."""
        names = [h for h in str(hosts or "").replace(",", " ").split() if h]
        ok, output = core.make_certificates(names, server_config=self._server_config,
                                            make_certs=self._make_certs, certs_dir=self._certs_dir)
        return {"ok": ok, "output": output}

    # the window

    def _attach(self, window):
        self._window = window

    def _on_closing(self):
        """pywebview's closing event: False keeps the window open while apps run, and the page asks."""
        if self._quitting or not self.running():
            return True
        window = self._window
        if window is not None:
            # evaluate_js waits for the page, which needs the GUI thread this handler is on
            threading.Thread(target=window.evaluate_js, args=("askClose()",), daemon=True).start()
        return False

    def quit(self):
        """Stop every app, then close the window."""
        self.stop_all(wait=True)
        self._quitting = True
        if self._window is not None:
            # after this call has answered the page: an answer to a closed window would wait forever
            timer = threading.Timer(0.2, self._window.destroy)
            timer.daemon = True
            timer.start()
        return True
