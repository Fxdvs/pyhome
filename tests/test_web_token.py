"""server/handlers/web_handler.py: the dashboard API behind the server's TOKEN."""
import asyncio
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from fastapi import HTTPException  # noqa: E402
from shared import config  # noqa: E402
from handlers import client_handler, web_handler  # noqa: E402
from helpers import run_tests  # noqa: E402

INDEX = os.path.join(ROOT_DIR, "server", "web", "index.html")


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": 0, **values}, f)
    config.init(tmp, path)


def status_of(authorization):
    """The status require_token answers with, None when it lets the request through."""
    try:
        asyncio.run(web_handler.require_token(authorization))
    except HTTPException as e:
        return e.status_code
    return None


def read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def test_token_matches_only_the_server_token(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    assert client_handler.token_matches("s3cret")
    for given in ("wrong", "", None, 5, "s3cret ", "S3CRET"):
        assert not client_handler.token_matches(given), given


def test_token_matches_nothing_without_a_server_token(tmp):
    for values in ({}, {"TOKEN": ""}, {"TOKEN": None}):
        use_server_config(tmp, **values)
        assert not client_handler.token_required(), values
        # an empty server token must never be "matched" by an empty header
        assert not client_handler.token_matches(""), values
        assert not client_handler.token_matches(None), values


def test_bearer_token(tmp):
    assert web_handler.bearer_token("Bearer abc") == "abc"
    assert web_handler.bearer_token("bearer abc") == "abc"
    assert web_handler.bearer_token("Bearer  abc ") == "abc"
    for header in (None, "", "Bearer", "Bearer ", "Basic abc", "abc", 5):
        assert web_handler.bearer_token(header) is None, header


def test_require_token_with_a_server_token(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    assert status_of("Bearer s3cret") is None
    for header in (None, "", "Bearer wrong", "s3cret", "Basic s3cret", "Bearer "):
        assert status_of(header) == 401, header


def test_require_token_without_a_server_token(tmp):
    use_server_config(tmp, TOKEN="")
    for header in (None, "Bearer anything", "garbage"):
        assert status_of(header) is None, header


def test_401_asks_for_a_bearer_token(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    try:
        asyncio.run(web_handler.require_token(None))
    except HTTPException as e:
        assert e.detail == "token required" and e.headers == {"WWW-Authenticate": "Bearer"}, (e.detail, e.headers)
    else:
        raise AssertionError("require_token let a request without a token through")


def test_error_body_shape(tmp):
    error = HTTPException(status_code=401, detail="token required", headers={"WWW-Authenticate": "Bearer"})
    response = asyncio.run(web_handler.error_body(None, error))
    assert response.status_code == 401
    assert json.loads(response.body) == {"error": "token required"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_status_says_whether_a_token_is_needed(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    assert asyncio.run(web_handler.api_status()) == {"token_required": True}
    use_server_config(tmp, TOKEN="")
    assert asyncio.run(web_handler.api_status()) == {"token_required": False}


def test_only_the_data_is_protected(tmp):
    protected = {}
    for route in web_handler.app.routes:
        dependencies = getattr(route, "dependencies", None)
        if dependencies is not None:
            protected[route.path] = any(d.dependency is web_handler.require_token for d in dependencies)
    assert protected["/api/clients"] is True, protected
    assert protected["/api/status"] is False and protected["/"] is False, protected


def test_dashboard_warning(tmp):
    use_server_config(tmp, TOKEN="")
    assert "anyone who can reach the dashboard" in web_handler.dashboard_warning()
    use_server_config(tmp, TOKEN="s3cret")
    assert web_handler.dashboard_warning() is None


def test_handshake_still_refuses_what_it_refused(tmp):
    use_server_config(tmp, TOKEN="s3cret")
    assert client_handler.check_token({"token": "s3cret"}) is None
    assert client_handler.check_token({"token": "nope"}) == "wrong token"
    assert "needs a token" in client_handler.check_token({})


if __name__ == "__main__":
    sys.exit(run_tests(globals()))
