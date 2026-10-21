"""The server's memory: one SQLite database next to the config, pyhome.db.

SQLAlchemy 2.0 over SQLite. The tables are mapped as ORM classes below and
nothing else in the server imports sqlalchemy or knows SQL: the rest of the
code calls the functions here, so another database later means another
engine URL and this file, nothing else.

One engine, used only from the event loop. A write is one small row, well
under a millisecond with WAL, so it is not worth a thread or an async driver;
the sqlite3 driver's check_same_thread stays on, so a call from elsewhere
fails loudly instead of corrupting anything.
"""
import datetime
import json
import os
import sqlite3

from sqlalchemy import ForeignKey, Index, Text, create_engine, delete, event, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from shared.config import get_config, get_config_path

DB_NAME = "pyhome.db"
LEGACY_CLIENTS = "clients.json"
# how long the history is kept when the config does not say
DEFAULT_HISTORY_DAYS = 90

_engine = None


class StoreError(Exception):
    """The database cannot be used. The server must not start without it."""


# the ORM classes describe the tables the migrations below create; the
# annotations are how SQLAlchemy 2.0 learns the column types and NOT NULL
class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    device: Mapped[str | None] = mapped_column(Text)
    # a JSON list, the device's action names
    capabilities: Mapped[str] = mapped_column(Text)
    first_seen: Mapped[str] = mapped_column(Text)
    last_seen: Mapped[str] = mapped_column(Text)


class DeviceState(Base):
    __tablename__ = "device_state"

    client_id: Mapped[str] = mapped_column(Text, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True)
    # a JSON object
    state: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class StateHistory(Base):
    __tablename__ = "state_history"
    __table_args__ = (
        Index("state_history_client_at", "client_id", "at"),
        Index("state_history_at", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, ForeignKey("clients.id", ondelete="CASCADE"))
    at: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


def get_store_path():
    """pyhome.db next to the config in use, so a server started with --config keeps its own."""
    return os.path.join(os.path.dirname(get_config_path()), DB_NAME)


def now_iso():
    """The current time as ISO 8601 UTC text, which sorts correctly as text."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _migration_1(db):
    # plain DDL on purpose: a migration is history and must create exactly
    # what it created when it shipped, whatever the ORM classes say today
    db.exec_driver_sql("""
        CREATE TABLE clients (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            device       TEXT,
            capabilities TEXT NOT NULL,
            first_seen   TEXT NOT NULL,
            last_seen    TEXT NOT NULL
        )""")
    db.exec_driver_sql("""
        CREATE TABLE device_state (
            client_id  TEXT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
            state      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
    db.exec_driver_sql("""
        CREATE TABLE state_history (
            id        INTEGER PRIMARY KEY,
            client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            at        TEXT NOT NULL,
            state     TEXT NOT NULL,
            source    TEXT NOT NULL
        )""")
    db.exec_driver_sql("CREATE INDEX state_history_client_at ON state_history (client_id, at)")
    db.exec_driver_sql("CREATE INDEX state_history_at ON state_history (at)")


# MIGRATIONS[n] takes the database from version n to n + 1, never edit one that shipped
MIGRATIONS = [_migration_1]
SCHEMA_VERSION = len(MIGRATIONS)


def _make_engine(path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, record):
        # the sqlite3 driver would otherwise run DDL outside any transaction,
        # so a failed migration could not be rolled back; SQLAlchemy says BEGIN instead
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")    # readers never block the writer
        cursor.execute("PRAGMA synchronous = NORMAL")  # safe with WAL, much faster
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(connection):
        connection.exec_driver_sql("BEGIN")

    return engine


def _migrate(engine, path):
    with engine.connect() as db:
        version = db.exec_driver_sql("PRAGMA user_version").scalar()
    if version > SCHEMA_VERSION:
        raise StoreError(f"{os.path.basename(path)} is version {version}, "
                         f"this server knows up to {SCHEMA_VERSION}")
    for number in range(version, SCHEMA_VERSION):
        # each step in one transaction, a crash leaves the old version intact
        with engine.begin() as db:
            MIGRATIONS[number](db)
            db.exec_driver_sql(f"PRAGMA user_version = {number + 1}")


def open_store(path=None):
    """Open (and create or migrate) the database. Returns the number of clients imported from clients.json.

    Raises StoreError with the reason when the file cannot be used.
    """
    global _engine
    close_store()
    path = path or get_store_path()
    engine = _make_engine(path)
    try:
        _migrate(engine, path)
    except StoreError:
        engine.dispose()
        raise
    except (SQLAlchemyError, sqlite3.Error) as e:
        engine.dispose()
        reason = getattr(e, "orig", None) or e
        raise StoreError(f"{path} cannot be used: {reason}") from e
    _engine = engine
    return import_legacy_clients(os.path.dirname(path))


def close_store():
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def _session():
    if _engine is None:
        raise RuntimeError("store.open_store() was never called")
    return Session(_engine)


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
    with _session() as session, session.begin():
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("ID"):
                continue
            # a repeated ID in the old file is skipped, not an error
            result = session.execute(
                insert(Client)
                .values(id=str(entry["ID"]), name=str(entry.get("NAME") or entry["ID"]), device=None,
                        capabilities="[]", first_seen=stamp, last_seen=stamp)
                .on_conflict_do_nothing(index_elements=[Client.id]))
            imported += result.rowcount
    os.replace(legacy, legacy + ".imported")
    return imported


def upsert_client(client_id, name, device, capabilities):
    """Record a client that just connected: what it says now, first_seen kept, last_seen now."""
    stamp = now_iso()
    statement = insert(Client).values(
        id=str(client_id), name=str(name), device=device,
        capabilities=json.dumps(list(capabilities)), first_seen=stamp, last_seen=stamp)
    statement = statement.on_conflict_do_update(
        index_elements=[Client.id],
        set_={
            "name": statement.excluded.name,
            "device": statement.excluded.device,
            "capabilities": statement.excluded.capabilities,
            "last_seen": statement.excluded.last_seen,
        })
    with _session() as session, session.begin():
        session.execute(statement)


def touch_client(client_id):
    """last_seen is now, for a client that just disconnected."""
    with _session() as session, session.begin():
        session.execute(update(Client).where(Client.id == str(client_id)).values(last_seen=now_iso()))


def _client_dict(client):
    return {
        "id": client.id,
        "name": client.name,
        "device": client.device,
        "capabilities": json.loads(client.capabilities),
        "first_seen": client.first_seen,
        "last_seen": client.last_seen,
    }


def get_client(client_id):
    with _session() as session:
        client = session.get(Client, str(client_id))
        return _client_dict(client) if client else None


def list_clients():
    """Every known client, the most recently seen first."""
    with _session() as session:
        clients = session.scalars(select(Client).order_by(Client.last_seen.desc(), Client.id))
        return [_client_dict(client) for client in clients]


def count_clients():
    with _session() as session:
        return session.scalar(select(func.count()).select_from(Client))


def clear_clients():
    """Forget every client, and with them their state and history. Returns how many there were."""
    # the database's ON DELETE CASCADE removes the rest, foreign keys are on for every connection
    with _session() as session, session.begin():
        return session.execute(delete(Client)).rowcount


def _state_text(state):
    # sorted keys, so the same state is always the same text in the database
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


def get_state(client_id):
    """The last stored state of a client, or None when none was ever stored."""
    with _session() as session:
        row = session.get(DeviceState, str(client_id))
        return json.loads(row.state) if row else None


def save_state(client_id, state, source):
    """Store a client's state and, when it changed, add one history row with its source.

    Returns True when the state changed. The same state again (a repeated
    state request, a reconnect) writes nothing. The comparison is on the
    parsed JSON, so key order does not matter.
    """
    client_id = str(client_id)
    stamp = now_iso()
    with _session() as session, session.begin():
        row = session.get(DeviceState, client_id)
        if row is not None and json.loads(row.state) == state:
            return False
        text = _state_text(state)
        if row is None:
            session.add(DeviceState(client_id=client_id, state=text, updated_at=stamp))
        else:
            row.state = text
            row.updated_at = stamp
        session.add(StateHistory(client_id=client_id, at=stamp, state=text, source=str(source)))
    return True


def get_history(client_id, limit=50):
    """The newest history entries of a client first, at most limit."""
    with _session() as session:
        rows = session.scalars(
            select(StateHistory)
            .where(StateHistory.client_id == str(client_id))
            # the id breaks ties within one second, a later row is a later change
            .order_by(StateHistory.at.desc(), StateHistory.id.desc())
            .limit(limit))
        return [{"at": row.at, "state": json.loads(row.state), "source": row.source} for row in rows]


def count_history():
    with _session() as session:
        return session.scalar(select(func.count()).select_from(StateHistory))


def history_days():
    """HISTORY_DAYS from the config: 90 when missing or not a number, never below 0."""
    try:
        days = int(get_config("HISTORY_DAYS", DEFAULT_HISTORY_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_HISTORY_DAYS
    return max(days, 0)


def prune_history(days, now=None):
    """Delete history older than days. 0 or less keeps none. Returns how many rows went."""
    with _session() as session, session.begin():
        statement = delete(StateHistory)
        if days > 0:
            now = now or datetime.datetime.now(datetime.timezone.utc)
            cutoff = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            # ISO 8601 text sorts like the time it names, so < compares times
            statement = statement.where(StateHistory.at < cutoff)
        return session.execute(statement).rowcount
