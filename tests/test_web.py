"""server/handlers/web_handler.py: the API shape and the page it serves."""
import asyncio
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from handlers import client_handler, web_handler  # noqa: E402

INDEX = os.path.join(ROOT_DIR, "server", "web", "index.html")


def read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def test_api_includes_device_fields(tmp, store_db):
    client_handler.connected_clients.clear()
    client_handler.connected_clients[("127.0.0.1", 5000)] = {
        "writer": None, "id": "lamp", "name": "Lamp", "device": "light",
        "capabilities": ["turn_on"], "last_state": {"on": True},
    }
    store_db.upsert_client("lamp", "Lamp", "light", ["turn_on"])
    last_seen = store_db.get_client("lamp")["last_seen"]
    assert web_handler.serialize_clients() == [{
        "id": "lamp", "name": "Lamp", "online": True, "host": "127.0.0.1", "port": 5000,
        "device": "light", "capabilities": ["turn_on"], "last_state": {"on": True}, "last_seen": last_seen,
    }]


def test_api_defaults_for_a_client_without_device(tmp, store_db):
    client_handler.connected_clients.clear()
    client_handler.connected_clients[("127.0.0.1", 5001)] = {"writer": None, "id": "c", "name": "Chat"}
    client = web_handler.serialize_clients()[0]
    assert client["device"] is None and client["capabilities"] == [] and client["last_state"] is None, client


def test_home_serves_the_designed_page(tmp):
    response = asyncio.run(web_handler.home())
    assert os.path.samefile(response.path, INDEX), response.path
    assert response.media_type == "text/html", response.media_type


def test_page_reads_the_api_and_escapes(tmp):
    page = read_index()
    assert 'fetch("/api/clients"' in page
    assert "const esc =" in page


def test_demo_data_only_outside_the_server(tmp):
    page = read_index()
    # a stopped server must not look like three devices online
    assert 'location.protocol === "file:"' in page
    assert "Server nedostupný" in page


def test_thermostat_off_is_shown_as_off(tmp):
    assert "Vypnutý" in read_index()


def test_api_lists_offline_clients_after_online_ones(tmp, store_db):
    client_handler.connected_clients.clear()
    for client_id, seen in (("old", "2026-01-01T00:00:00Z"), ("recent", "2026-10-01T00:00:00Z"), ("lamp", "2026-02-01T00:00:00Z")):
        store_db.upsert_client(client_id, client_id.title(), "light", ["turn_on"])
        with __import__("sqlite3").connect(os.path.join(tmp, "pyhome.db")) as db:
            db.execute("UPDATE clients SET last_seen = ? WHERE id = ?", (seen, client_id))
    store_db.save_state("recent", {"on": True}, "client")
    client_handler.connected_clients[("127.0.0.1", 5000)] = {
        "writer": None, "id": "lamp", "name": "Lamp", "device": "light",
        "capabilities": ["turn_on"], "last_state": {"on": False},
    }
    clients = web_handler.serialize_clients()
    assert [(c["id"], c["online"]) for c in clients] == [("lamp", True), ("recent", False), ("old", False)]
    recent = clients[1]
    assert recent["host"] is None and recent["port"] is None, recent
    assert recent["last_state"] == {"on": True} and recent["last_seen"] == "2026-10-01T00:00:00Z", recent
    assert clients[2]["last_state"] is None


def test_offline_states_take_one_query(tmp, store_db):
    import sqlalchemy

    client_handler.connected_clients.clear()
    for n in range(20):
        store_db.upsert_client(f"c{n}", f"C{n}", "light", [])
        store_db.save_state(f"c{n}", {"n": n}, "client")
    statements = []

    def count(conn, cursor, statement, *args):
        statements.append(statement)

    sqlalchemy.event.listen(store_db._engine, "before_cursor_execute", count)
    try:
        web_handler.serialize_clients()
    finally:
        sqlalchemy.event.remove(store_db._engine, "before_cursor_execute", count)
    # the client list and every state, not one query per client
    assert len([s for s in statements if s.lstrip().upper().startswith("SELECT")]) == 2, statements


def test_history_endpoint(tmp, store_db):
    store_db.upsert_client("lamp", "Lamp", "light", [])
    for level in range(5):
        store_db.save_state("lamp", {"level": level}, "console")
    body = asyncio.run(web_handler.api_history("lamp", "2"))
    assert [e["state"]["level"] for e in body["history"]] == [4, 3], body
    assert set(body["history"][0]) == {"at", "state", "source"}
    assert len(asyncio.run(web_handler.api_history("lamp"))["history"]) == 5


def test_history_endpoint_refusals(tmp, store_db):
    import json as _json
    store_db.upsert_client("lamp", "Lamp", "light", [])
    for limit, reason in (("0", "limit must be from 1 to 500"), ("501", "limit must be from 1 to 500"),
                          ("many", "limit must be a whole number")):
        response = asyncio.run(web_handler.api_history("lamp", limit))
        assert response.status_code == 400 and _json.loads(response.body) == {"error": reason}, limit
    response = asyncio.run(web_handler.api_history("nobody"))
    assert response.status_code == 404 and _json.loads(response.body) == {"error": "no known client with id 'nobody'"}
    route = next(r for r in web_handler.app.routes if getattr(r, "path", "") == "/api/clients/{client_id}/history")
    assert [d.dependency for d in route.dependencies] == [web_handler.require_token]


def test_page_shows_offline_clients(tmp):
    page = read_index()
    assert "const isOffline = (c) => c.online === false;" in page
    assert '"Offline, naposledy "' in page
    assert "return controls && !isOffline(c) &&" in page
    assert 'if (isOffline(c)) fresh.classList.add("offline");' in page
    assert '"<small> online z "' in page
