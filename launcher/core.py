"""What the launcher does, without any window: configs, tokens, certificates and the apps it starts.

The window only calls these functions, so everything here is tested on its
own, and a different window later reuses all of it.
"""
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import unicodedata

# the repo root, one folder up from this package
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the shared package sits there, like for the apps
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.config import ID_PATTERN, RESERVED_IDS, copy_example, id_warning  # noqa: E402

SERVER_DIR = os.path.join(ROOT_DIR, "server")
CLIENT_DIR = os.path.join(ROOT_DIR, "client")
SERVER_CONFIG = os.path.join(SERVER_DIR, "data", "config.json")
CLIENT_DATA_DIR = os.path.join(CLIENT_DIR, "data")
DEVICES_DIR = os.path.join(CLIENT_DIR, "devices")
SERVER_CERTS_DIR = os.path.join(SERVER_DIR, "data", "certs")
MAKE_CERTS = os.path.join(SERVER_DIR, "make_certs.py")

# only exists on windows, elsewhere the apps share the launcher's terminal
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

# how often the status column is refreshed, in milliseconds
POLL_MS = 1000

# Popen returns as soon as the server process exists, well before it has
# imported fastapi/uvicorn and started listening. A client started right away
# would fail its first connection attempt and then sit out its own retry
# delay, so give the server a head start before starting any client.
SERVER_HEAD_START_MS = 2000

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
    """One entry per *.json in data_dir, sorted by file name.

    Two configs sharing a non-empty id would collapse into one row wherever
    the id is the key (the dashboard, clients.json, `send <id>`), so both are
    flagged with an error instead of silently letting that happen. An id
    that breaks the id rule only gets a note, the config still runs.
    """
    if not os.path.isdir(data_dir):
        return []

    entries = []
    for file in sorted(os.listdir(data_dir)):
        # the examples are templates in git, not instances to run
        if not file.endswith(".json") or file.endswith(".example.json"):
            continue

        path = os.path.join(data_dir, file)
        entry = {"file": file, "path": path, "name": None, "device": None, "id": None, "error": None, "note": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry["name"] = data.get("NAME")
            entry["device"] = data.get("DEVICE") or None
            entry["id"] = data.get("ID") or None
            if entry["id"]:
                entry["note"] = id_warning(entry["id"])
        except (OSError, ValueError, AttributeError):
            # AttributeError: valid JSON that is not an object has no .get
            entry["error"] = "invalid JSON"
        entries.append(entry)

    seen = {}
    for entry in entries:
        if entry["id"]:
            seen[entry["id"]] = seen.get(entry["id"], 0) + 1
    for entry in entries:
        if entry["id"] and seen[entry["id"]] > 1:
            entry["error"] = f"duplicate ID {entry['id']}"

    return entries


def build_command(config_path):
    return [python_executable(), "app.py", "--config", config_path]


def head_start_ms(server_started):
    """0, unless server_started, then SERVER_HEAD_START_MS."""
    return SERVER_HEAD_START_MS if server_started else 0


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


# Configs

def ensure_default_configs(paths=None):
    """Make the server's and the default client's config.json from their examples when missing.

    A fresh checkout has only the examples, which are in git; the real
    configs hold the token and are not. Returns the paths made.
    """
    paths = paths or (SERVER_CONFIG, os.path.join(CLIENT_DATA_DIR, "config.json"))
    return [path for path in paths if copy_example(path)]


# a whole TCP or UDP port number
PORT_RANGE = range(1, 65536)


class ConfigError(Exception):
    """A form that cannot be saved. errors maps each field to what is wrong with it."""

    def __init__(self, errors):
        super().__init__("; ".join(f"{field}: {reason}" for field, reason in errors.items()))
        self.errors = errors


def read_config(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def write_config(path, data):
    """Write the whole file at once: a crash mid write leaves the old file, never half a new one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(temporary, path)


def id_from_name(name):
    """The id a name suggests: Spálňa svetlo -> spalna-svetlo. Empty when nothing usable is left."""
    # NFKD splits á into a and its accent, which encoding to ascii then drops
    plain = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def list_devices(devices_dir=DEVICES_DIR):
    """The device packages a client can load: every folder in client/devices with an __init__.py."""
    if not os.path.isdir(devices_dir):
        return []
    return sorted(name for name in os.listdir(devices_dir)
                  if not name.startswith("_") and os.path.isfile(os.path.join(devices_dir, name, "__init__.py")))


def parse_port(value):
    """value as a port number, or None when it is not one."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if port in PORT_RANGE and str(value).strip().isdigit() else None


def generate_token():
    """A token as the README suggests making one: 16 random bytes, URL safe."""
    return secrets.token_urlsafe(16)


def server_token(server_config=SERVER_CONFIG):
    """The TOKEN of the server in this checkout, or "" when it has none or no config."""
    try:
        return str(read_config(server_config).get("TOKEN") or "")
    except (OSError, ValueError):
        return ""


def validate_client(fields, existing_ids, devices):
    """{field: reason} for every field of a client form that cannot be saved. Empty when all is well.

    existing_ids are the ids of the other configs, not the one being edited.
    """
    errors = {}
    if not str(fields.get("name") or "").strip():
        errors["name"] = "Názov je povinný"

    client_id = str(fields.get("id") or "")
    if not client_id:
        errors["id"] = "ID je povinné"
    elif not ID_PATTERN.fullmatch(client_id):
        errors["id"] = "Len malé písmená a-z, číslice a pomlčky, napríklad spalna-svetlo"
    elif client_id in RESERVED_IDS or client_id == "config":
        errors["id"] = f"ID {client_id} je vyhradené, vyber iné"
    elif client_id in existing_ids:
        errors["id"] = f"ID {client_id} už má iný klient"

    device = fields.get("device") or ""
    if device and device not in devices:
        errors["device"] = f"Zariadenie {device} neexistuje"

    if not str(fields.get("host") or "").strip():
        errors["host"] = "Adresa servera je povinná"
    if parse_port(fields.get("port")) is None:
        errors["port"] = "Port je číslo od 1 do 65535"
    return errors


def save_client(fields, data_dir=CLIENT_DATA_DIR, devices=None, ca_source=None, original_path=None):
    """Validate a client form and write its config as <id>.json. Returns the path written.

    With fields["tls"], ca_source (the server's ca.crt) is copied next to the
    config and TLS_CA points at it. Raises ConfigError, writing nothing, when
    any field is wrong. Editing (original_path) under a new id moves the file.
    """
    devices = list_devices() if devices is None else devices
    path = os.path.join(data_dir, f"{fields.get('id')}.json")
    existing = {e["id"] for e in list_client_configs(data_dir)
                if e["id"] and not (original_path and os.path.samefile(e["path"], original_path))}
    errors = validate_client(fields, existing, devices)
    if not errors and os.path.exists(path) and not (original_path and os.path.samefile(path, original_path)):
        errors["id"] = f"Súbor {os.path.basename(path)} už existuje"

    tls = bool(fields.get("tls"))
    ca_source = ca_source or os.path.join(SERVER_CERTS_DIR, "ca.crt")
    if tls and not os.path.isfile(ca_source):
        errors["tls"] = "Server ešte nemá certifikáty, vytvor ich v nastaveniach servera"
    if errors:
        raise ConfigError(errors)

    if tls:
        os.makedirs(os.path.join(data_dir, "certs"), exist_ok=True)
        shutil.copyfile(ca_source, os.path.join(data_dir, "certs", "ca.crt"))

    data = {}
    if original_path:
        # keys the form does not know about stay as they were
        data = read_config(original_path)
    data.update({
        "ID": fields["id"],
        "NAME": str(fields["name"]).strip(),
        "TYPE": "client",
        "DEVICE": fields.get("device") or "",
        "VERSION": data.get("VERSION") or example_version(data_dir),
        "HOST": str(fields["host"]).strip(),
        "PORT": parse_port(fields["port"]),
        "TOKEN": str(fields.get("token") or ""),
        "TLS_CA": "certs/ca.crt" if tls else "",
    })
    write_config(path, data)
    if original_path and not os.path.samefile(original_path, path):
        os.remove(original_path)
    return path


def example_version(data_dir):
    """VERSION of the example config in data_dir, what a new config starts as."""
    try:
        return read_config(os.path.join(data_dir, "config.example.json")).get("VERSION", "")
    except (OSError, ValueError):
        return ""


def validate_server(fields):
    errors = {}
    if not str(fields.get("name") or "").strip():
        errors["name"] = "Názov je povinný"
    port, web_port = parse_port(fields.get("port")), parse_port(fields.get("web_port"))
    if port is None:
        errors["port"] = "Port je číslo od 1 do 65535"
    if web_port is None:
        errors["web_port"] = "Port je číslo od 1 do 65535"
    if port is not None and port == web_port:
        errors["web_port"] = "Dashboard potrebuje iný port ako klienti"
    try:
        if int(fields.get("history_days")) < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors["history_days"] = "Počet dní je celé číslo 0 alebo viac"
    return errors


def save_server(fields, path=SERVER_CONFIG):
    """Validate the server form and write its settings into path, keeping every other key."""
    errors = validate_server(fields)
    if errors:
        raise ConfigError(errors)
    data = read_config(path) if os.path.exists(path) else {}
    data.update({
        "NAME": str(fields["name"]).strip(),
        "PORT": parse_port(fields["port"]),
        "WEB_PORT": parse_port(fields["web_port"]),
        "TOKEN": str(fields.get("token") or ""),
        "HISTORY_DAYS": int(fields["history_days"]),
    })
    write_config(path, data)
    return path


def make_certificates(hosts=(), server_config=SERVER_CONFIG, make_certs=MAKE_CERTS, certs_dir=SERVER_CERTS_DIR):
    """Run make_certs.py and point the server config at what it made. Returns (ok, its output).

    It keeps an existing authority, so running it again renews only the server certificate.
    """
    command = [python_executable(), make_certs, "--dir", certs_dir]
    for host in hosts:
        command += ["--host", host]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    if result.returncode != 0:
        return False, output
    data = read_config(server_config) if os.path.exists(server_config) else {}
    data["TLS_CERT"] = "certs/server.crt"
    data["TLS_KEY"] = "certs/server.key"
    write_config(server_config, data)
    return True, output
