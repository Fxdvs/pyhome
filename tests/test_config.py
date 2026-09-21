"""shared/config.py: choosing the config file and stamping an id."""
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from shared import config  # noqa: E402
from helpers import run_tests  # noqa: E402


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
    path = os.path.join(tmp, "new.json")
    write_json(path, {"NAME": "New", "DEVICE": "light"})
    config.init(tmp, path)

    new_id = config.get_config("ID")
    assert isinstance(new_id, str) and len(new_id) == 8, new_id
    int(new_id, 16)  # hex, raises otherwise

    saved = read_json(path)
    assert saved == {"ID": new_id, "NAME": "New", "DEVICE": "light"}, saved
    assert list(saved)[0] == "ID", "ID should be the first key"


def test_empty_id_is_generated(tmp):
    path = os.path.join(tmp, "empty.json")
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


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
