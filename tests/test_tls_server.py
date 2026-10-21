"""server/handlers/tls.py: the server's TLS context and what it says at startup."""
import datetime
import json
import os
import ssl
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from shared import config  # noqa: E402
from handlers import tls  # noqa: E402
import make_certs  # noqa: E402


def use_server_config(tmp, **values):
    path = os.path.join(tmp, "server.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ID": "s", "NAME": "Server", "TYPE": "server", "VERSION": "test",
                   "HOST": "127.0.0.1", "PORT": 0, **values}, f)
    config.init(tmp, path)


def refused(tmp, **values):
    use_server_config(tmp, **values)
    try:
        tls.server_context()
    except tls.TLSConfigError as e:
        return str(e)
    raise AssertionError(f"{values} should not give a context")


def test_no_tls(tmp):
    for values in ({}, {"TLS_CERT": "", "TLS_KEY": ""}):
        use_server_config(tmp, **values)
        assert tls.tls_files() is None and tls.server_context() is None, values
        assert tls.startup_lines() == [
            (True, "No TLS_CERT set, the token and every message cross the network in plain text")]


def test_context_from_the_made_files(tmp):
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    use_server_config(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
    context = tls.server_context()
    assert isinstance(context, ssl.SSLContext)
    assert tls.tls_files() == (os.path.join(tmp, "certs", "server.crt"), os.path.join(tmp, "certs", "server.key"))


def test_one_of_two_is_refused(tmp):
    assert refused(tmp, TLS_CERT="certs/server.crt") == "TLS_KEY is empty, TLS needs both TLS_CERT and TLS_KEY"
    assert refused(tmp, TLS_KEY="certs/server.key") == "TLS_CERT is empty, TLS needs both TLS_CERT and TLS_KEY"


def test_missing_file_is_refused(tmp):
    message = refused(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
    assert message.startswith("TLS file not found: "), message


def test_key_of_another_certificate_is_refused(tmp):
    make_certs.make_certs(os.path.join(tmp, "a"), ["localhost"])
    make_certs.make_certs(os.path.join(tmp, "b"), ["localhost"])
    message = refused(tmp, TLS_CERT="a/server.crt", TLS_KEY="b/server.key")
    assert message.startswith("TLS_CERT and TLS_KEY cannot be used together: "), message


def test_broken_file_is_refused(tmp):
    with open(os.path.join(tmp, "junk.crt"), "w", encoding="utf-8") as f:
        f.write("junk\n")
    message = refused(tmp, TLS_CERT="junk.crt", TLS_KEY="junk.crt")
    assert message.startswith("TLS_CERT and TLS_KEY cannot be used together: "), message


def test_startup_lines(tmp):
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    use_server_config(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
    expiry = tls.cert_expiry(os.path.join(tmp, "certs", "server.crt"))

    lines = tls.startup_lines()
    assert lines == [(False, f"TLS on, certificate valid until {expiry.date().isoformat()}")], lines

    soon = tls.startup_lines(now=expiry - datetime.timedelta(days=10))
    assert soon[1] == (True, "The TLS certificate ends in 10 days, renew it with py server/make_certs.py"), soon

    over = tls.startup_lines(now=expiry + datetime.timedelta(days=3))
    assert over[1] == (True, "The TLS certificate has expired, renew it with py server/make_certs.py"), over


def test_ca_file_next_to_the_certificate(tmp):
    make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    use_server_config(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
    assert tls.ca_file() == os.path.join(tmp, "certs", "ca.crt")
    os.remove(os.path.join(tmp, "certs", "ca.crt"))
    assert tls.ca_file() is None
    use_server_config(tmp)
    assert tls.ca_file() is None


def test_fingerprint_matches_make_certs(tmp):
    ca_cert, _, _ = make_certs.make_certs(os.path.join(tmp, "certs"), ["localhost"])
    assert tls.fingerprint(os.path.join(tmp, "certs", "ca.crt")) == make_certs.fingerprint(ca_cert)


def test_uvicorn_options(tmp):
    use_server_config(tmp)
    assert tls.uvicorn_options() == {}
    use_server_config(tmp, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
    assert tls.uvicorn_options() == {
        "ssl_certfile": os.path.join(tmp, "certs", "server.crt"),
        "ssl_keyfile": os.path.join(tmp, "certs", "server.key"),
    }
