"""TLS for the server: the context from TLS_CERT and TLS_KEY, and what to say about it at startup."""
import datetime
import os
import ssl

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from shared.config import get_config_file

# a certificate this close to its end gets a warning at every start
EXPIRY_WARNING_DAYS = 30


class TLSConfigError(Exception):
    """TLS_CERT or TLS_KEY is set but cannot be used. The server must not start without it."""


def tls_files():
    """(cert path, key path), or None when the server has no TLS. TLSConfigError when only one is set."""
    cert, key = get_config_file("TLS_CERT"), get_config_file("TLS_KEY")
    if cert is None and key is None:
        return None
    if cert is None or key is None:
        missing = "TLS_CERT" if cert is None else "TLS_KEY"
        raise TLSConfigError(f"{missing} is empty, TLS needs both TLS_CERT and TLS_KEY")
    return cert, key


def server_context():
    """The SSLContext for the client listener, or None without TLS. TLSConfigError when it cannot be built."""
    files = tls_files()
    if files is None:
        return None
    cert, key = files
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(cert, key)
    except FileNotFoundError as e:
        raise TLSConfigError(f"TLS file not found: {e.filename}") from e
    except ssl.SSLError as e:
        # a broken file, or a key that belongs to another certificate
        raise TLSConfigError(f"TLS_CERT and TLS_KEY cannot be used together: {e.reason or e}") from e
    return context


def ca_file():
    """The authority's ca.crt next to TLS_CERT, where make_certs.py puts it, or None."""
    files = tls_files()
    if files is None:
        return None
    path = os.path.join(os.path.dirname(files[0]), "ca.crt")
    return path if os.path.isfile(path) else None


def fingerprint(path):
    """SHA-256 of the certificate at path as AB:CD:..., what a phone shows before trusting it."""
    with open(path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return ":".join(f"{b:02X}" for b in cert.fingerprint(hashes.SHA256()))


def uvicorn_options():
    """The ssl options for uvicorn.Config: the same files as the client listener, or none."""
    files = tls_files()
    if files is None:
        return {}
    return {"ssl_certfile": files[0], "ssl_keyfile": files[1]}


def cert_expiry(path):
    """When the certificate at path stops being valid, as an aware UTC datetime."""
    with open(path, "rb") as f:
        return x509.load_pem_x509_certificate(f.read()).not_valid_after_utc


def startup_lines(now=None):
    """[(is_warning, text)] the server prints about TLS when it starts."""
    files = tls_files()
    if files is None:
        return [(True, "No TLS_CERT set, the token and every message cross the network in plain text")]

    expiry = cert_expiry(files[0])
    lines = [(False, f"TLS on, certificate valid until {expiry.date().isoformat()}")]
    left = expiry - (now or datetime.datetime.now(datetime.timezone.utc))
    renew = "renew it with py server/make_certs.py"
    if left <= datetime.timedelta(0):
        # clients will refuse it, say so before they do
        lines.append((True, f"The TLS certificate has expired, {renew}"))
    elif left <= datetime.timedelta(days=EXPIRY_WARNING_DAYS):
        lines.append((True, f"The TLS certificate ends in {left.days} days, {renew}"))
    return lines
