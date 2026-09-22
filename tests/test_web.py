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
from helpers import run_tests  # noqa: E402

INDEX = os.path.join(ROOT_DIR, "server", "web", "index.html")


def read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def test_api_includes_device_fields(tmp):
    client_handler.connected_clients.clear()
    client_handler.connected_clients[("127.0.0.1", 5000)] = {
        "writer": None, "id": "lamp", "name": "Lamp", "device": "light",
        "capabilities": ["turn_on"], "last_state": {"on": True},
    }
    assert web_handler.serialize_clients() == [{
        "id": "lamp", "name": "Lamp", "host": "127.0.0.1", "port": 5000,
        "device": "light", "capabilities": ["turn_on"], "last_state": {"on": True},
    }]


def test_api_defaults_for_a_client_without_device(tmp):
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


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
