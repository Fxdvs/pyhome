"""Makes the certificates TLS needs: a private authority for this house and a server certificate.

    py server/make_certs.py [--host NAME_OR_IP ...] [--new-ca] [--dir FOLDER]

Running it again keeps the authority and only makes a new server certificate,
which is how it is renewed or fixed after the server's address changed.
Phones and clients trust ca.crt once and never need anything new.
"""
import datetime
import ipaddress
import os
import re
import socket
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
sys.path.insert(0, ROOT_DIR)

from shared.network import get_local_ip  # noqa: E402

# the config's folder, TLS_CERT and TLS_KEY are written relative to it
DATA_DIR = os.path.join(APP_DIR, "data")
CERTS_DIR = os.path.join(DATA_DIR, "certs")

CA_DAYS = 3650
# the longest a server certificate may live for apple devices to accept it
SERVER_DAYS = 825

# one part of a host name: letters, digits, - and _ inside, at most 63 long
LABEL = re.compile(r"[A-Za-z0-9]([A-Za-z0-9_-]{0,61}[A-Za-z0-9])?")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def new_key():
    return ec.generate_private_key(ec.SECP256R1())


def default_hosts():
    """The names a browser on the LAN may use for this computer."""
    hostname = socket.gethostname()
    hosts = ["localhost", "127.0.0.1"]
    if hostname:
        hosts += [hostname, f"{hostname}.local"]
    hosts.append(get_local_ip())
    return hosts


def unique(items):
    """items without repeats, first occurrence kept, compared case insensitively."""
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def san_entry(host):
    """An IP address entry for an address, a DNS entry for a name, None for neither."""
    try:
        return x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        # x509 wants plain ascii names, a host name with diacritics goes in punycode
        name = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    # a name with a space or other junk would be in the certificate and match nothing
    if not all(LABEL.fullmatch(label) for label in name.split(".")):
        return None
    return x509.DNSName(name)


def usable_hosts(hosts):
    """(usable, skipped): the hosts that can go in a certificate, and the others."""
    usable, skipped = [], []
    for host in unique(hosts):
        (usable if san_entry(host) is not None else skipped).append(host)
    return usable, skipped


def make_authority(name):
    """(key, certificate) of a new authority valid for CA_DAYS."""
    key = new_key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    start = now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(start + datetime.timedelta(days=CA_DAYS))
        # path_length 0: it signs server certificates, never another authority
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_server_cert(ca_key, ca_cert, hosts):
    """(key, certificate) for the server, signed by the authority, naming every host that is usable."""
    entries = [san_entry(h) for h in usable_hosts(hosts)[0]]
    key = new_key()
    start = now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pyhome server")]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(start + datetime.timedelta(days=SERVER_DAYS))
        .add_extension(x509.SubjectAlternativeName(entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def fingerprint(cert):
    """SHA-256 of the certificate as AB:CD:..., what a phone shows before trusting it."""
    return ":".join(f"{b:02X}" for b in cert.fingerprint(hashes.SHA256()))


def cert_names(cert):
    """The host names and addresses a certificate is valid for, as text."""
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return [str(n.value) for n in names]


def write_cert(path, cert):
    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def write_key(path, key):
    data = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
    # readable by this account only where the OS knows such a thing, windows ignores the mode
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def load_authority(certs_dir):
    """(key, certificate) of the authority in certs_dir, or None when there is none.

    Raises ValueError when only one of the two files is there, a half authority
    cannot sign anything and must not be silently replaced.
    """
    key_path = os.path.join(certs_dir, "ca.key")
    cert_path = os.path.join(certs_dir, "ca.crt")
    has_key, has_cert = os.path.exists(key_path), os.path.exists(cert_path)
    if not has_key and not has_cert:
        return None
    if not (has_key and has_cert):
        missing = "ca.key" if not has_key else "ca.crt"
        raise ValueError(f"{missing} is missing in {certs_dir}, run with --new-ca to start over")
    with open(key_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return key, cert


def config_value(path):
    """path as it goes into server/data/config.json: relative to its folder when inside it."""
    try:
        relative = os.path.relpath(path, DATA_DIR)
    except ValueError:
        # windows: another drive than the project has no relative path to it
        return path.replace("\\", "/")
    if relative.startswith(".."):
        return path.replace("\\", "/")
    return relative.replace("\\", "/")


def make_certs(certs_dir, hosts, new_ca=False):
    """Write the certificates into certs_dir. Returns (ca_cert, server_cert, made_new_ca)."""
    os.makedirs(certs_dir, exist_ok=True)
    authority = None if new_ca else load_authority(certs_dir)
    made_new_ca = authority is None
    if made_new_ca:
        authority = make_authority(f"pyhome CA {socket.gethostname()}".strip())
        write_key(os.path.join(certs_dir, "ca.key"), authority[0])
        write_cert(os.path.join(certs_dir, "ca.crt"), authority[1])

    ca_key, ca_cert = authority
    key, cert = make_server_cert(ca_key, ca_cert, hosts)
    write_key(os.path.join(certs_dir, "server.key"), key)
    write_cert(os.path.join(certs_dir, "server.crt"), cert)
    return ca_cert, cert, made_new_ca


def parse_args(argv):
    """(hosts given with --host, new_ca, certs_dir). SystemExit with a message on bad arguments."""
    hosts, new_ca, certs_dir = [], False, CERTS_DIR
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--new-ca":
            new_ca = True
        elif arg in ("--host", "--dir"):
            if not args:
                sys.exit(f"{arg} needs a value")
            value = args.pop(0)
            if arg == "--host":
                hosts.append(value)
            else:
                certs_dir = os.path.abspath(value)
        else:
            sys.exit(f"unknown argument '{arg}'\n{__doc__}")
    return hosts, new_ca, certs_dir


def main(argv):
    hosts, new_ca, certs_dir = parse_args(argv)
    try:
        ca_cert, cert, made_new_ca = make_certs(certs_dir, default_hosts() + hosts, new_ca)
    except ValueError as e:
        sys.exit(str(e))

    ca_path = os.path.join(certs_dir, "ca.crt")
    until = cert.not_valid_after_utc.date().isoformat()
    print(f"Certificates written to {certs_dir}")
    print(f"  server.crt valid until {until} for {', '.join(cert_names(cert))}")
    for host in usable_hosts(default_hosts() + hosts)[1]:
        print(f"  skipped '{host}', it is not a host name or an address")
    if made_new_ca:
        print(f"  ca.crt is new, fingerprint {fingerprint(ca_cert)}")
        if new_ca:
            print("  !! A new authority: every client and phone needs the new ca.crt,"
                  " the old one no longer works.")
    else:
        print("  ca.crt kept, clients and phones need nothing new")
    print()
    print("Next:")
    print(f'  1. server/data/config.json:  "TLS_CERT": "{config_value(os.path.join(certs_dir, "server.crt"))}",'
          f' "TLS_KEY": "{config_value(os.path.join(certs_dir, "server.key"))}"')
    print(f"  2. copy {ca_path} to every client's data/certs/ folder")
    print('     and set "TLS_CA": "certs/ca.crt" in its config')
    print("  3. install ca.crt on phones that open the dashboard, see README")
    print("Keep ca.key and server.key private.")


if __name__ == "__main__":
    main(sys.argv[1:])
