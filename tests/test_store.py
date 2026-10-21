"""server/handlers/store.py: the SQLite database, its schema, migrations and clients."""
import contextlib
import io
import json
import os
import sqlite3
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from handlers import store  # noqa: E402
from helpers import run_tests  # noqa: E402


def use_server_config(tmp):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server"}, f)
    config.init(tmp, path)


def db_path(tmp):
    return os.path.join(tmp, "pyhome.db")


def raw(tmp):
    """A separate connection, to look at the file the way any SQLite browser would."""
    return sqlite3.connect(db_path(tmp))


def write_legacy(tmp, text):
    with open(os.path.join(tmp, "clients.json"), "w", encoding="utf-8") as f:
        f.write(text)


def test_store_sits_next_to_the_config(tmp):
    use_server_config(tmp)
    assert store.get_store_path() == db_path(tmp)


def test_fresh_database(tmp):
    assert store.open_store(db_path(tmp)) == 0
    store.close_store()
    with raw(tmp) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 1
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert tables == {"clients", "device_state", "state_history"}, tables
        indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'")}
        assert indexes == {"state_history_client_at", "state_history_at"}, indexes
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_opening_again_changes_nothing(tmp):
    store.open_store(db_path(tmp))
    store.upsert_client("lamp", "Lamp", "light", ["turn_on"])
    store.open_store(db_path(tmp))
    assert [c["id"] for c in store.list_clients()] == ["lamp"]
    store.close_store()


def test_newer_database_is_refused(tmp):
    with raw(tmp) as db:
        db.execute("PRAGMA user_version = 7")
    try:
        store.open_store(db_path(tmp))
    except store.StoreError as e:
        assert str(e) == "pyhome.db is version 7, this server knows up to 1", e
    else:
        raise AssertionError("a database from a newer version must not be used")


def test_a_file_that_is_not_sqlite_is_refused(tmp):
    with open(db_path(tmp), "w", encoding="utf-8") as f:
        f.write("this is not a database, just some text that is long enough to have a header\n" * 20)
    try:
        store.open_store(db_path(tmp))
    except store.StoreError as e:
        assert "cannot be used" in str(e), e
    else:
        raise AssertionError("expected StoreError")


def test_a_failed_migration_leaves_the_old_version(tmp):
    def broken(db):
        db.execute("CREATE TABLE half (x)")
        raise sqlite3.OperationalError("disk on fire")

    original = list(store.MIGRATIONS)
    store.MIGRATIONS.append(broken)
    store.SCHEMA_VERSION = len(store.MIGRATIONS)
    try:
        store.open_store(db_path(tmp))
    except store.StoreError as e:
        assert "disk on fire" in str(e), e
    else:
        raise AssertionError("expected StoreError")
    finally:
        store.MIGRATIONS[:] = original
        store.SCHEMA_VERSION = len(original)
    with raw(tmp) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT name FROM sqlite_master WHERE name = 'half'").fetchone() is None


def test_upsert_keeps_first_seen(tmp):
    store.open_store(db_path(tmp))
    store.upsert_client("lamp", "Lamp", "light", ["turn_on"])
    first = store.get_client("lamp")
    with raw(tmp) as db:
        db.execute("UPDATE clients SET first_seen = '2026-01-01T00:00:00Z', last_seen = '2026-01-01T00:00:00Z'")
    store.upsert_client("lamp", "Kuchyňa svetlo", "light", ["turn_on", "turn_off"])
    again = store.get_client("lamp")
    store.close_store()
    assert first["capabilities"] == ["turn_on"] and first["device"] == "light"
    assert again["first_seen"] == "2026-01-01T00:00:00Z", again
    assert again["last_seen"] > "2026-01-01T00:00:00Z", again
    assert again["name"] == "Kuchyňa svetlo" and again["capabilities"] == ["turn_on", "turn_off"], again


def test_client_without_device(tmp):
    store.open_store(db_path(tmp))
    store.upsert_client(5, "Chat", None, [])
    client = store.get_client("5")
    store.close_store()
    assert client["id"] == "5" and client["device"] is None and client["capabilities"] == [], client


def test_touch_sets_last_seen(tmp):
    store.open_store(db_path(tmp))
    store.upsert_client("lamp", "Lamp", "light", [])
    with raw(tmp) as db:
        db.execute("UPDATE clients SET last_seen = '2026-01-01T00:00:00Z'")
    store.touch_client("lamp")
    store.touch_client("nobody")  # unknown ids are ignored
    last_seen = store.get_client("lamp")["last_seen"]
    store.close_store()
    assert last_seen > "2026-01-01T00:00:00Z", last_seen


def test_list_and_count(tmp):
    store.open_store(db_path(tmp))
    for client_id, seen in (("a", "2026-01-01T00:00:00Z"), ("b", "2026-03-01T00:00:00Z"), ("c", "2026-02-01T00:00:00Z")):
        store.upsert_client(client_id, client_id.upper(), None, [])
        with raw(tmp) as db:
            db.execute("UPDATE clients SET last_seen = ? WHERE id = ?", (seen, client_id))
    ids = [c["id"] for c in store.list_clients()]
    count = store.count_clients()
    store.close_store()
    assert ids == ["b", "c", "a"], ids
    assert count == 3


def test_clear_takes_state_and_history_with_it(tmp):
    store.open_store(db_path(tmp))
    store.upsert_client("lamp", "Lamp", "light", [])
    with raw(tmp) as db:
        db.execute("INSERT INTO device_state VALUES ('lamp', '{}', 'x')")
        db.execute("INSERT INTO state_history (client_id, at, state, source) VALUES ('lamp', 'x', '{}', 'client')")
    assert store.clear_clients() == 1
    assert store.clear_clients() == 0
    store.close_store()
    with raw(tmp) as db:
        assert db.execute("SELECT COUNT(*) FROM device_state").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM state_history").fetchone()[0] == 0


def test_legacy_clients_json_is_imported_once(tmp):
    write_legacy(tmp, json.dumps([{"ID": "1", "NAME": "Kuchyňa"}, {"ID": "2", "NAME": "Spálňa"}, {"NAME": "no id"}, "junk"]))
    assert store.open_store(db_path(tmp)) == 2
    clients = {c["id"]: c for c in store.list_clients()}
    store.close_store()
    assert set(clients) == {"1", "2"} and clients["1"]["name"] == "Kuchyňa", clients
    assert clients["1"]["capabilities"] == [] and clients["1"]["device"] is None
    assert not os.path.exists(os.path.join(tmp, "clients.json"))
    assert os.path.exists(os.path.join(tmp, "clients.json.imported"))

    # a clients.json that shows up again is not imported into a non-empty table
    write_legacy(tmp, json.dumps([{"ID": "3", "NAME": "Late"}]))
    assert store.open_store(db_path(tmp)) == 0
    assert store.get_client("3") is None
    store.close_store()
    assert os.path.exists(os.path.join(tmp, "clients.json"))


def test_broken_legacy_file_imports_nothing_and_is_kept(tmp):
    for text in ("{not json", json.dumps({"ID": "1"}), ""):
        write_legacy(tmp, text)
        assert store.open_store(db_path(tmp)) == 0, text
        assert store.count_clients() == 0
        store.close_store()
        # renamed all the same, it was looked at once and kept as the backup
        assert os.path.exists(os.path.join(tmp, "clients.json.imported")), text
        os.remove(os.path.join(tmp, "clients.json.imported"))


def test_calls_before_open_fail_loudly(tmp):
    store.close_store()
    try:
        store.count_clients()
    except RuntimeError as e:
        assert "open_store" in str(e), e
    else:
        raise AssertionError("expected RuntimeError")


def test_database_files_are_ignored_by_git(tmp):
    import subprocess
    paths = ["server/data/pyhome.db", "server/data/pyhome.db-wal", "server/data/pyhome.db-shm",
             "server/data/clients.json.imported"]
    try:
        result = subprocess.run(["git", "check-ignore", *paths], cwd=ROOT_DIR, capture_output=True, text=True)
    except FileNotFoundError:
        return  # no git on this machine, nothing to check
    assert result.stdout.split() == paths, result.stdout


def test_now_iso(tmp):
    stamp = store.now_iso()
    assert len(stamp) == 20 and stamp.endswith("Z") and stamp[10] == "T", stamp


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
