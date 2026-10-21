"""End to end: v1.2 Part 3 "Done when", the dashboard over HTTPS with real processes."""
import os
import ssl
import sys
import urllib.error
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))

from e2e import wait_for, with_system  # noqa: E402
import make_certs  # noqa: E402

TOKEN = "s3cret-https"


def test_dashboard_over_https(tmp):
    def scenario(system):
        make_certs.make_certs(os.path.join(system.tmp, "certs"), ["localhost", "127.0.0.1"])
        ca = os.path.join(system.tmp, "certs", "ca.crt")
        system.start_server(TOKEN=TOKEN, TLS_CERT="certs/server.crt", TLS_KEY="certs/server.key")
        system.start_client("e2e-light", "light", TOKEN=TOKEN, TLS_CA="certs/ca.crt")
        wait_for(lambda: system.client("e2e-light"), "the light on the https dashboard")

        # full verification, host name included, at both names in the certificate
        context = ssl.create_default_context(cafile=ca)
        for host in ("localhost", "127.0.0.1"):
            with urllib.request.urlopen(f"https://{host}:{system.web_port}/api/status", timeout=5, context=context) as r:
                assert r.status == 200, host

        # controls work over https as they did over http
        status, body = system.post("/api/clients/e2e-light/do", {"action": "turn_on"}, TOKEN)
        assert status == 200 and body["state"]["on"] is True, body

        # ca.crt for phones, without a token, byte for byte the file
        with urllib.request.urlopen(f"https://localhost:{system.web_port}/ca.crt", timeout=5, context=context) as r:
            with open(ca, "rb") as f:
                assert r.read() == f.read()

        # plain http to the same port is not answered
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{system.web_port}/api/status", timeout=5)
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        else:
            raise AssertionError("the dashboard must not answer plain HTTP")

        # an untrusting client is refused, the certificate is not a public one
        try:
            urllib.request.urlopen(f"https://localhost:{system.web_port}/api/status", timeout=5,
                                   context=ssl.create_default_context())
        except urllib.error.URLError as e:
            assert isinstance(e.reason, ssl.SSLCertVerificationError), e
        else:
            raise AssertionError("a browser without ca.crt must not trust it")

        log = system.log("server")
        assert f"https://localhost:{system.web_port}" in log, log
        with open(ca, "rb") as f:
            ca_cert = make_certs.x509.load_pem_x509_certificate(f.read())
        assert make_certs.fingerprint(ca_cert) in log, "the fingerprint to compare on the phone"

    with_system(tmp, scenario)


def test_dashboard_without_tls_stays_http(tmp):
    def scenario(system):
        system.start_server()
        with urllib.request.urlopen(f"http://127.0.0.1:{system.web_port}/api/status", timeout=5) as r:
            assert r.status == 200
        assert f"http://localhost:{system.web_port}" in system.log("server")
        assert "/ca.crt" not in system.log("server")

    with_system(tmp, scenario)
