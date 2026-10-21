"""The server's memory: one SQLite database next to the config, pyhome.db.

Nothing else in the server imports sqlite3. The rest of the code calls the
functions here and never sees SQL, so another database later replaces this
file and nothing else.

One connection, used only from the event loop. A write is one small row, well
under a millisecond with WAL, so it is not worth a thread; check_same_thread
stays on so a call from elsewhere fails loudly instead of corrupting anything.
"""
import datetime
import json
import os
import sqlite3

from shared.config import get_config_path

DB_NAME = "pyhome.db"
LEGACY_CLIENTS = "clients.json"

_connection = None


class StoreError(Exception):
    """The database cannot be used. The server must not start without it."""


def get_store_path():
    """pyhome.db next to the config in use, so a server started with --config keeps its own."""
    return os.path.join(os.path.dirname(get_config_path()), DB_NAME)


def now_iso():
    """The current time as ISO 8601 UTC text, which sorts correctly as text."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _migration_1(db):
    db.execute("""
        CREATE TABLE clients (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            device       TEXT,
            capabilities TEXT NOT NULL,
            first_seen   TEXT NOT NULL,
            last_seen    TEXT NOT NULL
        )""")
    db.execute("""
        CREATE TABLE device_state (
            client_id  TEXT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
            state      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
    db.execute("""
        CREATE TABLE state_history (
            id        INTEGER PRIMARY KEY,
            client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            at        TEXT NOT NULL,
            state     TEXT NOT NULL,
            source    TEXT NOT NULL
        )""")
    db.execute("CREATE INDEX state_history_client_at ON state_history (client_id, at)")
    db.execute("CREATE INDEX state_history_at ON state_history (at)")


# MIGRATIONS[n] takes the database from version n to n + 1, never edit one that shipped
MIGRATIONS = [_migration_1]
SCHEMA_VERSION = len(MIGRATIONS)


def _migrate(db, path):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise StoreError(f"{os.path.basename(path)} is version {version}, "
                         f"this server knows up to {SCHEMA_VERSION}")
    for number in range(version, SCHEMA_VERSION):
        # each step in one transaction, a crash leaves the old version intact
        db.execute("BEGIN")
        try:
            MIGRATIONS[number](db)
            db.execute(f"PRAGMA user_version = {number + 1}")
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise


def open_store(path=None):
    """Open (and create or migrate) the database. Returns the number of clients imported from clients.json.

    Raises StoreError with the reason when the file cannot be used.
    """
    global _connection
    close_store()
    path = path or get_store_path()
    try:
        db = sqlite3.connect(path, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = NORMAL")
        db.execute("PRAGMA foreign_keys = ON")
        _migrate(db, path)
    except sqlite3.Error as e:
        raise StoreError(f"{path} cannot be used: {e}") from e
    _connection = db
    return import_legacy_clients(os.path.dirname(path))


def close_store():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def _db():
    if _connection is None:
        raise RuntimeError("store.open_store() was never called")
    return _connection


def import_legacy_clients(folder):
    """Insert the clients of an old clients.json once, then rename it. Returns how many were imported.

    Runs only while the clients table is empty. The file is renamed, not
    deleted: it is the backup, and the rename is what makes this run once.
    """
    legacy = os.path.join(folder, LEGACY_CLIENTS)
    if not os.path.exists(legacy) or count_clients() > 0:
        return 0
    try:
        with open(legacy, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError):
        entries = []
    if not isinstance(entries, list):
        entries = []

    stamp = now_iso()
    imported = 0
    db = _db()
    db.execute("BEGIN")
    try:
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("ID"):
                continue
            cursor = db.execute(
                "INSERT OR IGNORE INTO clients (id, name, device, capabilities, first_seen, last_seen)"
                " VALUES (?, ?, NULL, '[]', ?, ?)",
                (str(entry["ID"]), str(entry.get("NAME") or entry["ID"]), stamp, stamp))
            imported += cursor.rowcount
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    os.replace(legacy, legacy + ".imported")
    return imported


def upsert_client(client_id, name, device, capabilities):
    """Record a client that just connected: what it says now, first_seen kept, last_seen now."""
    stamp = now_iso()
    _db().execute(
        "INSERT INTO clients (id, name, device, capabilities, first_seen, last_seen)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (id) DO UPDATE SET name = excluded.name, device = excluded.device,"
        " capabilities = excluded.capabilities, last_seen = excluded.last_seen",
        (str(client_id), str(name), device, json.dumps(list(capabilities)), stamp, stamp))


def touch_client(client_id):
    """last_seen is now, for a client that just disconnected."""
    _db().execute("UPDATE clients SET last_seen = ? WHERE id = ?", (now_iso(), str(client_id)))


def _client_row(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "device": row["device"],
        "capabilities": json.loads(row["capabilities"]),
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
    }


def get_client(client_id):
    row = _db().execute("SELECT * FROM clients WHERE id = ?", (str(client_id),)).fetchone()
    return _client_row(row) if row else None


def list_clients():
    """Every known client, the most recently seen first."""
    rows = _db().execute("SELECT * FROM clients ORDER BY last_seen DESC, id").fetchall()
    return [_client_row(row) for row in rows]


def count_clients():
    return _db().execute("SELECT COUNT(*) FROM clients").fetchone()[0]


def clear_clients():
    """Forget every client, and with them their state and history. Returns how many there were."""
    return _db().execute("DELETE FROM clients").rowcount
