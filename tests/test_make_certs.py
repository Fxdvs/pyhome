"""server/make_certs.py: the private authority and the server certificate."""
import asyncio
import contextlib
import datetime
import io
import os
import ssl
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, TESTS_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "server"))
sys.path.insert(0, ROOT_DIR)

from cryptography import x509  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID  # noqa: E402
import make_certs  # noqa: E402

FILES = ["ca.crt", "ca.key", "server.crt", "server.key"]


def load(certs_dir, name):
    with open(os.path.join(certs_dir, name), "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def read_bytes(certs_dir, name):
    with open(os.path.join(certs_dir, name), "rb") as f:
        return f.read()


def run_main(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        make_certs.main(list(argv))
    return out.getvalue()


def days(cert):
    return (cert.not_valid_after_utc - cert.not_valid_before_utc).days


def test_writes_four_files(tmp):
    make_certs.make_certs(tmp, ["localhost"])
    assert sorted(os.listdir(tmp)) == FILES, os.listdir(tmp)
    if os.name == "posix":
        # keys readable by this account only
        for name in ("ca.key", "server.key"):
            assert os.stat(os.path.join(tmp, name)).st_mode & 0o077 == 0, name


def test_authority(tmp):
    make_certs.make_certs(tmp, ["localhost"])
    ca = load(tmp, "ca.crt")
    constraints = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert constraints.ca is True and constraints.path_length == 0
    usage = ca.extensions.get_extension_for_class(x509.KeyUsage).value
    assert usage.key_cert_sign and usage.crl_sign
    assert ca.issuer == ca.subject
    assert days(ca) == make_certs.CA_DAYS


def test_server_certificate(tmp):
    make_certs.make_certs(tmp, ["localhost", "127.0.0.1", "dom.lan", "192.168.1.20"])
    ca, cert = load(tmp, "ca.crt"), load(tmp, "server.crt")
    cert.verify_directly_issued_by(ca)
    constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert constraints.ca is False
    usage = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(usage) == [ExtendedKeyUsageOID.SERVER_AUTH]
    assert make_certs.cert_names(cert) == ["localhost", "127.0.0.1", "dom.lan", "192.168.1.20"]
    assert days(cert) == make_certs.SERVER_DAYS


def test_second_run_keeps_the_authority(tmp):
    make_certs.make_certs(tmp, ["localhost"])
    ca_before = read_bytes(tmp, "ca.crt")
    key_before = read_bytes(tmp, "ca.key")
    server_before = read_bytes(tmp, "server.crt")

    _, _, made_new_ca = make_certs.make_certs(tmp, ["localhost", "10.0.0.5"])

    assert made_new_ca is False
    assert read_bytes(tmp, "ca.crt") == ca_before and read_bytes(tmp, "ca.key") == key_before
    assert read_bytes(tmp, "server.crt") != server_before
    # the phones' old ca.crt still trusts the new server certificate
    load(tmp, "server.crt").verify_directly_issued_by(load(tmp, "ca.crt"))
    assert "10.0.0.5" in make_certs.cert_names(load(tmp, "server.crt"))


def test_new_ca_replaces_the_authority(tmp):
    make_certs.make_certs(tmp, ["localhost"])
    ca_before = read_bytes(tmp, "ca.crt")
    _, _, made_new_ca = make_certs.make_certs(tmp, ["localhost"], new_ca=True)
    assert made_new_ca is True and read_bytes(tmp, "ca.crt") != ca_before
    load(tmp, "server.crt").verify_directly_issued_by(load(tmp, "ca.crt"))


def test_half_an_authority_is_refused(tmp):
    make_certs.make_certs(tmp, ["localhost"])
    os.remove(os.path.join(tmp, "ca.key"))
    ca_before = read_bytes(tmp, "ca.crt")
    try:
        make_certs.make_certs(tmp, ["localhost"])
    except ValueError as e:
        assert "ca.key is missing" in str(e) and "--new-ca" in str(e), e
    else:
        raise AssertionError("a lone ca.crt must not be silently replaced")
    assert read_bytes(tmp, "ca.crt") == ca_before


def test_san_entries(tmp):
    assert make_certs.san_entry("192.168.1.20") == x509.IPAddress(__import__("ipaddress").ip_address("192.168.1.20"))
    assert make_certs.san_entry("::1") is not None
    assert make_certs.san_entry("dom.lan") == x509.DNSName("dom.lan")
    assert make_certs.san_entry("DOM-PC") == x509.DNSName("DOM-PC")
    assert make_certs.san_entry("kúpeľňa") == x509.DNSName("xn--kpea-qra42bic")
    for bad in ("Dóm PC", "a b", "-dom", "dom-", "dom..lan", "", "a" * 64):
        assert make_certs.san_entry(bad) is None, bad


def test_usable_hosts(tmp):
    usable, skipped = make_certs.usable_hosts(["localhost", "LOCALHOST", "dom", "Dóm PC", "dom", ""])
    assert usable == ["localhost", "dom"] and skipped == ["Dóm PC"], (usable, skipped)


def test_default_hosts(tmp):
    hosts = make_certs.default_hosts()
    assert hosts[:2] == ["localhost", "127.0.0.1"], hosts
    hostname = __import__("socket").gethostname()
    if hostname:
        assert hostname in hosts and f"{hostname}.local" in hosts, hosts


def test_config_value(tmp):
    inside = os.path.join(make_certs.DATA_DIR, "certs", "server.crt")
    assert make_certs.config_value(inside) == "certs/server.crt"
    outside = os.path.join(tmp, "server.crt")
    assert make_certs.config_value(outside) == outside.replace("\\", "/")


def test_config_value_on_another_drive(tmp, monkeypatch):
    # what os.path.relpath does on windows for C:\\... against a project on D:\\...
    def other_drive(path, start=None):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(make_certs.os.path, "relpath", other_drive)
    path = os.path.join(tmp, "server.crt")
    assert make_certs.config_value(path) == path.replace("\\", "/")


def test_main_prints_the_steps(tmp):
    out = run_main("--dir", tmp, "--host", "dom.lan", "--host", "Dóm PC")
    assert f"Certificates written to {tmp}" in out
    assert "dom.lan" in out and "skipped 'Dóm PC'" in out
    assert "ca.crt is new, fingerprint " in out
    assert make_certs.fingerprint(load(tmp, "ca.crt")) in out
    assert '"TLS_CERT"' in out and '"TLS_KEY"' in out and '"TLS_CA": "certs/ca.crt"' in out
    assert "Keep ca.key and server.key private." in out

    again = run_main("--dir", tmp)
    assert "ca.crt kept, clients and phones need nothing new" in again
    assert "fingerprint" not in again

    loud = run_main("--dir", tmp, "--new-ca")
    assert "every client and phone needs the new ca.crt" in loud


def test_bad_arguments(tmp):
    for argv in (["--host"], ["--dir"], ["--nope"]):
        try:
            make_certs.parse_args(argv)
        except SystemExit as e:
            assert e.code, argv
        else:
            raise AssertionError(f"{argv} should have been refused")
    assert make_certs.parse_args(["--host", "a", "--host", "b", "--new-ca"])[:2] == (["a", "b"], True)


def test_python_ssl_trusts_it(tmp):
    """A real TLS handshake: the server's files load, and ca.crt verifies them, host name included."""
    make_certs.make_certs(tmp, ["localhost", "127.0.0.1"])
    server_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_ctx.load_cert_chain(os.path.join(tmp, "server.crt"), os.path.join(tmp, "server.key"))
    client_ctx = ssl.create_default_context(cafile=os.path.join(tmp, "ca.crt"))

    async def scenario():
        async def echo(reader, writer):
            writer.write(await reader.readline())
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(echo, "127.0.0.1", 0, ssl=server_ctx)
        port = server.sockets[0].getsockname()[1]
        async with server:
            reader, writer = await asyncio.open_connection(
                "localhost", port, ssl=client_ctx, server_hostname="localhost")
            writer.write(b"ahoj\n")
            await writer.drain()
            line = await reader.readline()
            writer.close()
            return line

    assert asyncio.run(scenario()) == b"ahoj\n"


def test_command_line(tmp):
    result = subprocess.run([sys.executable, os.path.join(ROOT_DIR, "server", "make_certs.py"), "--dir", tmp],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr
    assert sorted(os.listdir(tmp)) == FILES


def test_certs_are_ignored_by_git(tmp):
    paths = ["server/data/certs/ca.key", "server/data/certs/server.key", "client/data/certs/ca.crt"]
    try:
        result = subprocess.run(["git", "check-ignore", *paths], cwd=ROOT_DIR, capture_output=True, text=True)
    except FileNotFoundError:
        return  # no git on this machine, nothing to check
    assert result.stdout.split() == paths, result.stdout
