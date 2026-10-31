"""shared/config.py: choosing the config file and stamping an id."""
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from shared import config  # noqa: E402


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_default_path(tmp):
    config.init(tmp)
    assert config.get_config_path() == os.path.join(tmp, "data", "config.json")


def test_config_file_overrides_default(tmp):
    path = os.path.join(tmp, "kitchen.json")
    write_json(path, {"ID": "abc", "NAME": "Kitchen"})
    config.init(tmp, path)
    assert config.get_config_path() == path
    assert config.get_config("NAME") == "Kitchen"


def test_missing_id_is_generated_and_saved(tmp):
    # config.json says nothing about the device, so it gets a random id
    path = os.path.join(tmp, "config.json")
    write_json(path, {"NAME": "New", "DEVICE": "light"})
    config.init(tmp, path)

    new_id = config.get_config("ID")
    assert isinstance(new_id, str) and len(new_id) == 8, new_id
    int(new_id, 16)  # hex, raises otherwise

    saved = read_json(path)
    assert saved == {"ID": new_id, "NAME": "New", "DEVICE": "light"}, saved
    assert list(saved)[0] == "ID", "ID should be the first key"


def test_empty_id_is_generated(tmp):
    path = os.path.join(tmp, "config.json")
    write_json(path, {"NAME": "Empty", "ID": ""})
    config.init(tmp, path)
    assert len(config.get_config("ID")) == 8
    assert read_json(path)["ID"] == config.get_config("ID")


def test_existing_id_is_kept(tmp):
    path = os.path.join(tmp, "old.json")
    write_json(path, {"ID": "1", "NAME": "Old"})
    before = os.path.getmtime(path)
    config.init(tmp, path)
    assert config.get_config("ID") == "1"
    assert read_json(path) == {"ID": "1", "NAME": "Old"}
    assert os.path.getmtime(path) == before, "a config with an id is not rewritten"


def test_stamping_an_id_keeps_non_ascii_readable(tmp):
    path = os.path.join(tmp, "kitchen.json")
    write_json(path, {"NAME": "Kuchyňa"})
    config.init(tmp, path)
    config.get_config("ID")  # triggers the stamp-and-save on first load

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    assert "Kuchyňa" in raw, raw
    assert "\\u" not in raw, raw


def test_two_new_configs_get_different_ids(tmp):
    ids = []
    for name in ("a.json", "b.json"):
        path = os.path.join(tmp, name)
        write_json(path, {"NAME": name})
        config.init(tmp, path)
        ids.append(config.get_config("ID"))
    assert ids[0] != ids[1], ids


def test_empty_id_follows_the_file_name(tmp):
    path = os.path.join(tmp, "kuchyna-svetlo.json")
    write_json(path, {"NAME": "Kuchyňa svetlo", "ID": ""})
    config.init(tmp, path)
    assert config.get_config("ID") == "kuchyna-svetlo"
    assert read_json(path)["ID"] == "kuchyna-svetlo"


def test_file_name_id_is_lowercased(tmp):
    path = os.path.join(tmp, "Obyvacka-Termostat.json")
    write_json(path, {"NAME": "Obývačka"})
    config.init(tmp, path)
    assert config.get_config("ID") == "obyvacka-termostat"


def test_unusable_file_names_give_a_random_id(tmp):
    for name in ("config.json", "Kuchyňa 1.json", "kuchyna_svetlo.json", "-svetlo.json", "all.json"):
        path = os.path.join(tmp, name)
        write_json(path, {"NAME": "X"})
        config.init(tmp, path)
        new_id = config.get_config("ID")
        assert len(new_id) == 8, (name, new_id)
        int(new_id, 16)


def test_id_from_file_name(tmp):
    assert config.id_from_file_name(os.path.join(tmp, "spalna-svetlo.json")) == "spalna-svetlo"
    assert config.id_from_file_name("data/2.json") == "2"
    for name in ("config.json", "CONFIG.json", "a b.json", "a--b.json", "svetlo-.json", "all.json", "ľad.json"):
        assert config.id_from_file_name(name) is None, name


def test_id_warning(tmp):
    for good in ("kuchyna-svetlo", "1", "3f9a12bc", "a1-b2-c3"):
        assert config.id_warning(good) is None, good
    assert config.id_warning(1) is None
    assert config.id_warning("Kuchyňa 1") == \
        "ID 'Kuchyňa 1' does not follow the id rule (a-z, 0-9 and -), it cannot be typed in commands"
    # typeable, just off the convention: no claim it cannot be typed
    assert config.id_warning("Kuchyna") == "ID 'Kuchyna' does not follow the id rule (a-z, 0-9 and -)"
    assert config.id_warning("kuchyna_svetlo") == "ID 'kuchyna_svetlo' does not follow the id rule (a-z, 0-9 and -)"
    assert config.id_warning("all") == "ID 'all' is reserved for send all, choose another"


def test_config_file_paths(tmp):
    folder = os.path.join(tmp, "data")
    os.makedirs(folder)
    path = os.path.join(folder, "server.json")
    absolute = os.path.join(tmp, "elsewhere", "ca.crt")
    write_json(path, {"ID": "s", "TLS_CERT": "certs/server.crt", "TLS_CA": absolute, "TLS_KEY": ""})
    config.init(tmp, path)
    # relative to the config's folder, not to the working directory
    assert config.get_config_file("TLS_CERT") == os.path.join(folder, "certs", "server.crt")
    assert config.get_config_file("TLS_CA") == os.path.normpath(absolute)
    assert config.get_config_file("TLS_KEY") is None
    assert config.get_config_file("MISSING") is None


def test_argv_without_config(tmp):
    assert config.config_file_from_argv(["app.py"]) is None


def test_argv_with_absolute_config(tmp):
    path = os.path.join(tmp, "kitchen.json")
    write_json(path, {})
    assert config.config_file_from_argv(["app.py", "--config", path]) == path


def test_argv_relative_config_is_made_absolute(tmp):
    write_json(os.path.join(tmp, "kitchen.json"), {})
    os.chdir(tmp)
    result = config.config_file_from_argv(["app.py", "--config", "kitchen.json"])
    assert os.path.isabs(result), result
    assert os.path.samefile(result, os.path.join(tmp, "kitchen.json"))


def test_argv_config_without_value_exits(tmp):
    try:
        config.config_file_from_argv(["app.py", "--config"])
    except SystemExit:
        return
    raise AssertionError("expected SystemExit")


def test_argv_config_missing_file_exits(tmp):
    try:
        config.config_file_from_argv(["app.py", "--config", os.path.join(tmp, "nope.json")])
    except SystemExit:
        return
    raise AssertionError("expected SystemExit")


def test_default_config_made_from_example(tmp, capsys):
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    write_json(os.path.join(data_dir, "config.example.json"), {"ID": "", "NAME": "Example", "TOKEN": ""})
    config.init(tmp)
    path = os.path.join(data_dir, "config.json")
    assert read_json(path)["NAME"] == "Example"
    assert "from config.example.json" in capsys.readouterr().out


def test_existing_config_not_overwritten_by_example(tmp):
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    write_json(os.path.join(data_dir, "config.example.json"), {"NAME": "Example"})
    write_json(os.path.join(data_dir, "config.json"), {"NAME": "Mine"})
    config.init(tmp)
    assert read_json(os.path.join(data_dir, "config.json"))["NAME"] == "Mine"


def test_config_option_not_made_from_example(tmp):
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir)
    write_json(os.path.join(data_dir, "config.example.json"), {"NAME": "Example"})
    path = os.path.join(data_dir, "kitchen.json")
    config.init(tmp, path)
    assert not os.path.exists(path)


def test_repo_ships_examples_not_configs():
    root = os.path.dirname(TESTS_DIR)
    for side in ("server", "client"):
        example = read_json(os.path.join(root, side, "data", "config.example.json"))
        assert example.get("TOKEN", "") == "", f"{side} example must not carry a token"
