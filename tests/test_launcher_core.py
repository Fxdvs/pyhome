"""launcher/core.py: listing configs, handling processes, and making configs, without any window."""
import json
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, ROOT_DIR)

import pytest  # noqa: E402
from launcher import core as launcher  # noqa: E402

# no console windows popping up while the tests run
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_lists_client_configs(tmp):
    write(os.path.join(tmp, "b.json"), json.dumps({"NAME": "Plain"}))
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "Kitchen", "DEVICE": "light", "ID": "a1"}))
    write(os.path.join(tmp, "c.json"), "{not json")
    write(os.path.join(tmp, "notes.txt"), "ignored")

    entries = launcher.list_client_configs(tmp)

    assert [e["file"] for e in entries] == ["a.json", "b.json", "c.json"], entries
    a, b, c = entries
    assert a == {"file": "a.json", "path": os.path.join(tmp, "a.json"), "id": "a1",
                 "name": "Kitchen", "device": "light", "error": None, "note": None}, a
    assert b["name"] == "Plain" and b["device"] is None and b["error"] is None and b["id"] is None, b
    assert c["error"] == "invalid JSON" and c["name"] is None and c["id"] is None, c


def test_duplicate_ids_are_flagged(tmp):
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "A", "ID": "1"}))
    write(os.path.join(tmp, "b.json"), json.dumps({"NAME": "B", "ID": "1"}))
    write(os.path.join(tmp, "c.json"), json.dumps({"NAME": "C", "ID": "2"}))

    entries = launcher.list_client_configs(tmp)

    a, b, c = entries
    assert a["error"] == "duplicate ID 1", a
    assert b["error"] == "duplicate ID 1", b
    assert c["error"] is None, c


def test_an_id_off_the_rule_is_a_note_not_an_error(tmp):
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "A", "ID": "Kuchyňa 1"}))
    write(os.path.join(tmp, "b.json"), json.dumps({"NAME": "B", "ID": "kuchyna-svetlo"}))
    write(os.path.join(tmp, "c.json"), json.dumps({"NAME": "C"}))

    a, b, c = launcher.list_client_configs(tmp)

    assert a["error"] is None and "cannot be typed" in a["note"], a
    assert b["note"] is None and c["note"] is None, (b, c)


def test_missing_or_empty_ids_are_not_duplicates(tmp):
    write(os.path.join(tmp, "a.json"), json.dumps({"NAME": "A"}))
    write(os.path.join(tmp, "b.json"), json.dumps({"NAME": "B", "ID": ""}))

    entries = launcher.list_client_configs(tmp)

    assert entries[0]["error"] is None and entries[1]["error"] is None, entries


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


# making configs

def server_dir(tmp, **values):
    """A server data folder with a config and certificates, like make_certs.py leaves it."""
    folder = os.path.join(tmp, "server")
    os.makedirs(os.path.join(folder, "certs"))
    path = os.path.join(folder, "config.json")
    launcher.write_config(path, {"ID": "dom", "NAME": "Dom", "TYPE": "server", "PORT": 50000,
                                 "WEB_PORT": 50001, "TOKEN": "s3cret", "HISTORY_DAYS": 90, **values})
    write(os.path.join(folder, "certs", "ca.crt"), "-----BEGIN CERTIFICATE-----\nexample\n")
    return folder


def client_dir(tmp):
    folder = os.path.join(tmp, "client")
    os.makedirs(folder)
    write(os.path.join(folder, "config.example.json"), json.dumps({"ID": "", "VERSION": "1.4"}))
    return folder


def form(**values):
    return {"name": "Spálňa svetlo", "id": "spalna-svetlo", "device": "light", "host": "192.168.1.20",
            "port": "50000", "token": "s3cret", "tls": False, **values}


def test_id_from_name():
    assert launcher.id_from_name("Spálňa svetlo") == "spalna-svetlo"
    assert launcher.id_from_name("Obývačka  Termostat 2") == "obyvacka-termostat-2"
    assert launcher.id_from_name("  --Chodba / senzor--  ") == "chodba-senzor"
    assert launcher.id_from_name("ľščťžýáíé") == "lsctzyaie"
    assert launcher.id_from_name("???") == ""


def test_list_devices(tmp):
    devices = os.path.join(tmp, "devices")
    for name, init in (("light", True), ("thermostat", True), ("notes", False), ("_private", True)):
        os.makedirs(os.path.join(devices, name))
        if init:
            write(os.path.join(devices, name, "__init__.py"), "")
    write(os.path.join(devices, "__init__.py"), "")
    assert launcher.list_devices(devices) == ["light", "thermostat"]
    assert launcher.list_devices(os.path.join(tmp, "missing")) == []
    assert launcher.list_devices() == ["light", "thermostat"], "the real client/devices"


def test_examples_are_not_listed_as_clients(tmp):
    write(os.path.join(tmp, "config.example.json"), json.dumps({"ID": "", "NAME": "Client"}))
    write(os.path.join(tmp, "kuchyna-svetlo.json"), json.dumps({"ID": "kuchyna-svetlo", "NAME": "K"}))
    assert [e["file"] for e in launcher.list_client_configs(tmp)] == ["kuchyna-svetlo.json"]


def test_parse_port():
    assert launcher.parse_port("50000") == 50000 and launcher.parse_port(1) == 1
    for bad in ("0", "65536", "-1", "abc", "", None, "50000.5", " 12a"):
        assert launcher.parse_port(bad) is None, bad


def test_validate_client():
    devices = ["light", "thermostat"]
    assert launcher.validate_client(form(), set(), devices) == {}
    errors = launcher.validate_client(form(name=" ", id="Spálňa 1", device="toaster", host="", port="99999"), set(), devices)
    assert set(errors) == {"name", "id", "device", "host", "port"}, errors
    assert "už má iný klient" in launcher.validate_client(form(), {"spalna-svetlo"}, devices)["id"]
    for reserved in ("all", "config"):
        assert "vyhradené" in launcher.validate_client(form(id=reserved), set(), devices)["id"], reserved
    assert launcher.validate_client(form(device=""), set(), devices) == {}, "no device is allowed"


def test_save_client_writes_the_config(tmp):
    data_dir = client_dir(tmp)
    path = launcher.save_client(form(), data_dir, devices=["light"])
    assert path == os.path.join(data_dir, "spalna-svetlo.json")
    assert launcher.read_config(path) == {
        "ID": "spalna-svetlo", "NAME": "Spálňa svetlo", "TYPE": "client", "DEVICE": "light", "VERSION": "1.4",
        "HOST": "192.168.1.20", "PORT": 50000, "TOKEN": "s3cret", "TLS_CA": "",
    }
    with open(path, encoding="utf-8") as f:
        assert "Spálňa" in f.read(), "diacritics stay readable in the file"


def test_save_client_with_tls_copies_ca_crt(tmp):
    data_dir, server = client_dir(tmp), server_dir(tmp)
    path = launcher.save_client(form(tls=True), data_dir, devices=["light"],
                                ca_source=os.path.join(server, "certs", "ca.crt"))
    assert launcher.read_config(path)["TLS_CA"] == "certs/ca.crt"
    with open(os.path.join(data_dir, "certs", "ca.crt"), encoding="utf-8") as f:
        assert "example" in f.read()


def test_save_client_without_certificates_is_refused(tmp):
    data_dir = client_dir(tmp)
    with pytest.raises(launcher.ConfigError) as error:
        launcher.save_client(form(tls=True), data_dir, devices=["light"], ca_source=os.path.join(tmp, "missing.crt"))
    assert "certifikáty" in error.value.errors["tls"]
    assert os.listdir(data_dir) == ["config.example.json"], "nothing is written"


def test_save_client_refuses_and_writes_nothing(tmp):
    data_dir = client_dir(tmp)
    launcher.save_client(form(), data_dir, devices=["light"])
    with pytest.raises(launcher.ConfigError) as error:
        launcher.save_client(form(name="Druhé"), data_dir, devices=["light"])
    assert "už má iný klient" in error.value.errors["id"]
    assert launcher.read_config(os.path.join(data_dir, "spalna-svetlo.json"))["NAME"] == "Spálňa svetlo"


def test_editing_keeps_unknown_keys_and_can_rename(tmp):
    data_dir = client_dir(tmp)
    path = launcher.save_client(form(), data_dir, devices=["light"])
    data = launcher.read_config(path)
    data["CUSTOM"] = "kept"
    launcher.write_config(path, data)

    # the same id again is the same client, not a duplicate
    same = launcher.save_client(form(name="Spálňa lampa"), data_dir, devices=["light"], original_path=path)
    assert same == path and launcher.read_config(path)["CUSTOM"] == "kept"

    moved = launcher.save_client(form(id="spalna-lampa"), data_dir, devices=["light"], original_path=path)
    assert moved == os.path.join(data_dir, "spalna-lampa.json") and not os.path.exists(path)
    assert launcher.read_config(moved)["CUSTOM"] == "kept"


def test_generate_token():
    tokens = {launcher.generate_token() for _ in range(20)}
    assert len(tokens) == 20 and all(len(t) >= 20 for t in tokens)


def test_server_token(tmp):
    server = server_dir(tmp)
    assert launcher.server_token(os.path.join(server, "config.json")) == "s3cret"
    assert launcher.server_token(os.path.join(tmp, "missing.json")) == ""


def test_save_server_keeps_other_keys(tmp):
    path = os.path.join(server_dir(tmp), "config.json")
    launcher.save_server({"name": "Domček", "port": "50010", "web_port": "50011", "token": "new", "history_days": "30"}, path)
    data = launcher.read_config(path)
    assert (data["NAME"], data["PORT"], data["WEB_PORT"], data["TOKEN"], data["HISTORY_DAYS"]) == ("Domček", 50010, 50011, "new", 30)
    assert data["ID"] == "dom" and data["TYPE"] == "server"


def test_validate_server():
    good = {"name": "Dom", "port": "50000", "web_port": "50001", "token": "", "history_days": "90"}
    assert launcher.validate_server(good) == {}
    errors = launcher.validate_server({**good, "name": "", "web_port": "50000", "history_days": "-1"})
    assert set(errors) == {"name", "web_port", "history_days"}, errors
    assert "iný port" in errors["web_port"]


def test_make_certificates(tmp):
    pytest.importorskip("cryptography")
    server = server_dir(tmp)
    config = os.path.join(server, "config.json")
    certs = os.path.join(tmp, "fresh-certs")  # server_dir's ca.crt is a fake without a key
    ok, output = launcher.make_certificates(["dom.lan"], server_config=config, certs_dir=certs)
    assert ok, output
    assert "dom.lan" in output and "Certificates written to" in output
    data = launcher.read_config(config)
    assert (data["TLS_CERT"], data["TLS_KEY"]) == ("certs/server.crt", "certs/server.key")
    assert os.path.exists(os.path.join(certs, "server.crt"))


def test_make_certificates_reports_failure(tmp):
    pytest.importorskip("cryptography")
    server = server_dir(tmp)
    config = os.path.join(server, "config.json")
    ok, output = launcher.make_certificates(server_config=config, certs_dir=os.path.join(server, "certs"))
    assert not ok and "ca.key is missing" in output
    assert "TLS_CERT" not in launcher.read_config(config)


def test_ensure_default_configs(tmp):
    for folder in ("server", "client"):
        os.makedirs(os.path.join(tmp, folder))
        write(os.path.join(tmp, folder, "config.example.json"), json.dumps({"ID": "1", "NAME": folder}))
    paths = [os.path.join(tmp, "server", "config.json"), os.path.join(tmp, "client", "config.json")]
    write(paths[1], json.dumps({"ID": "mine"}))
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        made = launcher.ensure_default_configs(paths)
    assert made == [paths[0]], "an existing config is never overwritten"
    assert launcher.read_config(paths[0])["NAME"] == "server"
    assert launcher.read_config(paths[1]) == {"ID": "mine"}


def test_write_config_leaves_no_temporary_file(tmp):
    path = os.path.join(tmp, "a", "config.json")
    launcher.write_config(path, {"ID": "x"})
    assert os.listdir(os.path.join(tmp, "a")) == ["config.json"]
