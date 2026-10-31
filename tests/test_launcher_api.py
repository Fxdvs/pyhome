"""launcher/api.py, what the page calls, on a checkout of fake apps in a temp folder."""
import json
import os
import shutil
import sys
import time

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, ROOT_DIR)

from launcher.api import Api  # noqa: E402

# an app as the launcher sees one: prints who it is, answers input, ends on shutdown + y
FAKE_APP = """
import json, sys
config = json.load(open(sys.argv[2], encoding="utf-8"))
print("started " + config["NAME"], flush=True)
for line in sys.stdin:
    line = line.strip()
    if line == "shutdown":
        if sys.stdin.readline().strip() == "y":
            print(config["NAME"] + " is shutting down", flush=True)
            sys.exit(0)
    elif line == "fail":
        sys.exit(2)
    else:
        print("got " + line, flush=True)
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_json(path, data):
    write(path, json.dumps(data))


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def checkout(tmp, tls=False):
    """A pyhome folder with fake apps: a server and two clients, one of them broken."""
    root = os.path.join(tmp, "pyhome")
    write(os.path.join(root, "server", "app.py"), FAKE_APP)
    write(os.path.join(root, "client", "app.py"), FAKE_APP)
    write_json(os.path.join(root, "server", "data", "config.json"),
               {"ID": "dom", "NAME": "Dom", "TYPE": "server", "PORT": 50000, "WEB_PORT": 50001,
                "TOKEN": "s3cret", "HISTORY_DAYS": 90, **({"TLS_CERT": "certs/server.crt"} if tls else {})})
    write_json(os.path.join(root, "client", "data", "config.example.json"), {"VERSION": "1.4"})
    write_json(os.path.join(root, "client", "data", "kuchyna-svetlo.json"),
               {"ID": "kuchyna-svetlo", "NAME": "Kuchyňa svetlo", "DEVICE": "light", "HOST": "127.0.0.1",
                "PORT": 50000, "TOKEN": "s3cret", "TLS_CA": "", "EXTRA": 1})
    write(os.path.join(root, "client", "data", "zly.json"), "{ not json")
    for device in ("light", "thermostat"):
        write(os.path.join(root, "client", "devices", device, "__init__.py"), "")
    if tls:
        write(os.path.join(root, "server", "data", "certs", "ca.crt"), "-----BEGIN CERTIFICATE-----\n")
    return root


def wait_for(check, what, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


@pytest.fixture
def api(tmp):
    api = Api(checkout(tmp), head_start=0.2)
    yield api
    api.stop_all(wait=True)


def texts(api, key):
    return [text for _, text in api.output(key)["lines"]]


def test_apps_lists_the_server_first_then_clients(api):
    apps = api.apps()
    keys = [a["key"] for a in apps["apps"]]
    assert keys == ["server", "kuchyna-svetlo.json", "zly.json"], "examples are not apps"
    server, kitchen, broken = apps["apps"]
    assert (server["name"], server["kind"], server["chips"]) == ("Dom", "server", ["bez TLS", "token"])
    assert kitchen["sub"] == "light · kuchyna-svetlo.json" and kitchen["meta"] == "→ 127.0.0.1:50000"
    assert broken["error"] == "invalid JSON"
    assert all(a["status"]["state"] == "stopped" for a in apps["apps"])


def test_first_start_ticks_everything_that_can_run(api):
    apps = api.apps()
    assert [a["key"] for a in apps["apps"] if a["checked"]] == ["server", "kuchyna-svetlo.json"]
    assert apps["selected"] == "server"


def test_ticks_and_selection_are_remembered(tmp, api):
    api.check("kuchyna-svetlo.json", False)
    api.select("kuchyna-svetlo.json")
    again = Api(os.path.join(tmp, "pyhome"))
    apps = again.apps()
    assert [a["key"] for a in apps["apps"] if a["checked"]] == ["server"]
    assert apps["selected"] == "kuchyna-svetlo.json"
    assert read_json(os.path.join(tmp, "pyhome", "launcher", "state.json"))["selected"] == "kuchyna-svetlo.json"


def test_a_broken_state_file_is_ignored(tmp):
    root = checkout(tmp)
    write(os.path.join(root, "launcher", "state.json"), "[1, 2")
    assert Api(root).apps()["selected"] == "server"


def test_a_selection_that_is_gone_falls_back_to_the_server(api):
    api.select("gone.json")
    assert api.apps()["selected"] == "server"


def test_start_output_send_and_stop(api):
    assert api.start("server")
    wait_for(lambda: "started Dom" in texts(api, "server"), "the server")
    assert api.output("server")["status"]["state"] == "running"
    assert api.running() == ["server"]
    assert api.send("server", "do kuch turn_on")
    wait_for(lambda: "got do kuch turn_on" in texts(api, "server"), "the answer")
    assert api.stop("server")
    wait_for(lambda: api.output("server")["status"]["state"] == "stopped", "the stop")
    assert "Dom is shutting down" in texts(api, "server")


def test_unknown_or_stopped_apps(api):
    assert not api.start("../../etc/passwd") and not api.start("missing.json")
    assert api.output("kuchyna-svetlo.json") == {"lines": [], "last": 0,
                                                 "status": {"state": "stopped", "code": None, "uptime": None}}
    assert not api.send("kuchyna-svetlo.json", "x") and not api.stop("kuchyna-svetlo.json")


def test_run_checked_starts_the_server_first(api):
    assert api.run_checked() == ["server", "kuchyna-svetlo.json"]
    wait_for(lambda: "started Kuchyňa svetlo" in texts(api, "kuchyna-svetlo.json"), "the client")
    assert "started Dom" in texts(api, "server")
    assert sorted(api.running()) == ["kuchyna-svetlo.json", "server"]
    assert api.run_checked() == [], "nothing left to start"
    assert api.stop_all(wait=True) == 2
    assert api.running() == []


def test_a_failing_app_shows_as_exited(api):
    api.start("kuchyna-svetlo.json")
    wait_for(lambda: texts(api, "kuchyna-svetlo.json"), "the client")
    api.send("kuchyna-svetlo.json", "fail")
    wait_for(lambda: api.apps()["apps"][1]["status"]["state"] == "exited", "the exit")
    assert api.apps()["apps"][1]["status"]["code"] == 2


def test_new_client_form_takes_what_the_server_has(tmp):
    api = Api(checkout(tmp, tls=True))
    form = api.client_form()
    assert form["devices"] == ["light", "thermostat"]
    assert form["fields"] == {"name": "", "id": "", "device": "light", "host": "127.0.0.1", "port": "50000",
                              "use_server_token": True, "token": "", "tls": True}


def test_save_a_new_client_with_the_server_token_and_tls(tmp):
    root = checkout(tmp, tls=True)
    api = Api(root)
    assert api.suggest_id("Spálňa svetlo") == "spalna-svetlo"
    answer = api.save_client({"name": "Spálňa svetlo", "id": "spalna-svetlo", "device": "light",
                              "host": "192.168.1.20", "port": "50000", "use_server_token": True, "tls": True})
    assert answer == {"ok": True, "errors": {}, "key": "spalna-svetlo.json", "running": False}
    data = read_json(os.path.join(root, "client", "data", "spalna-svetlo.json"))
    assert (data["TOKEN"], data["TLS_CA"], data["VERSION"]) == ("s3cret", "certs/ca.crt", "1.4")
    assert os.path.isfile(os.path.join(root, "client", "data", "certs", "ca.crt"))
    apps = api.apps()
    assert apps["selected"] == "spalna-svetlo.json"
    assert next(a for a in apps["apps"] if a["key"] == "spalna-svetlo.json")["checked"]


def test_save_client_reports_every_wrong_field(api):
    answer = api.save_client({"name": "", "id": "kuchyna-svetlo", "device": "toaster", "host": "", "port": "0"})
    assert not answer["ok"]
    assert set(answer["errors"]) == {"name", "id", "device", "host", "port"}
    assert "už má iný klient" in answer["errors"]["id"]


def test_edit_a_running_client_under_a_new_id(tmp, api):
    api.start("kuchyna-svetlo.json")
    wait_for(lambda: texts(api, "kuchyna-svetlo.json"), "the client")
    form = api.client_form("kuchyna-svetlo.json")
    assert form["fields"]["name"] == "Kuchyňa svetlo" and form["fields"]["token"] == "s3cret"
    fields = {**form["fields"], "id": "kuchyna-lampa"}
    answer = api.save_client(fields, "kuchyna-svetlo.json")
    assert answer == {"ok": True, "errors": {}, "key": "kuchyna-lampa.json", "running": True}
    data_dir = os.path.join(tmp, "pyhome", "client", "data")
    assert not os.path.exists(os.path.join(data_dir, "kuchyna-svetlo.json"))
    assert read_json(os.path.join(data_dir, "kuchyna-lampa.json"))["EXTRA"] == 1
    # the running app and its output moved with the file
    assert api.running() == ["kuchyna-lampa.json"]
    assert "started Kuchyňa svetlo" in texts(api, "kuchyna-lampa.json")
    api.restart("kuchyna-lampa.json")
    wait_for(lambda: texts(api, "kuchyna-lampa.json").count("started Kuchyňa svetlo") == 2, "the restart")


def test_server_form_and_save(tmp, api):
    form = api.server_form()
    assert form["fields"] == {"name": "Dom", "port": "50000", "web_port": "50001", "token": "s3cret",
                              "history_days": "90"}
    bad = api.save_server({**form["fields"], "web_port": "50000"})
    assert not bad["ok"] and "web_port" in bad["errors"]
    token = api.generate_token()
    assert len(token) >= 16 and token != api.generate_token()
    assert api.save_server({**form["fields"], "name": "Domček", "token": token})["ok"]
    data = read_json(os.path.join(tmp, "pyhome", "server", "data", "config.json"))
    assert (data["NAME"], data["TOKEN"], data["ID"]) == ("Domček", token, "dom")


def test_make_certificates_through_the_api(tmp):
    pytest.importorskip("cryptography")
    root = checkout(tmp)
    shutil.copyfile(os.path.join(ROOT_DIR, "server", "make_certs.py"), os.path.join(root, "server", "make_certs.py"))
    shutil.copytree(os.path.join(ROOT_DIR, "shared"), os.path.join(root, "shared"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    api = Api(root)
    answer = api.make_certificates("dom.lan, 192.168.1.20")
    assert answer["ok"], answer["output"]
    assert "dom.lan" in answer["output"] and "192.168.1.20" in answer["output"]
    assert api.server_form()["tls"] and api.client_form()["server"]["tls"]


class FakeWindow:
    def __init__(self):
        self.scripts = []
        self.destroyed = False

    def evaluate_js(self, script):
        self.scripts.append(script)

    def destroy(self):
        self.destroyed = True


def test_closing_asks_while_apps_run(api):
    window = FakeWindow()
    api._attach(window)
    assert api._on_closing() is True, "nothing runs, close right away"
    api.start("server")
    wait_for(lambda: texts(api, "server"), "the server")
    assert api._on_closing() is False
    wait_for(lambda: window.scripts == ["askClose()"], "the question in the page")
    assert api.quit()
    wait_for(lambda: window.destroyed, "the window closed after quit answered")
    assert api.running() == [] and api._on_closing() is True


def test_nothing_private_is_exposed_to_the_page(api):
    # pywebview walks the public attributes of the api object and exposes them all
    public = [name for name in vars(api) if not name.startswith("_")]
    assert public == []
