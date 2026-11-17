"""Docker's health check: does the dashboard answer? Exit 0 when it does, 1 when it does not.

It asks the server it runs next to, on 127.0.0.1, so with TLS the
certificate is not checked: its names are the ones the house uses.
"""
import os
import ssl
import sys
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(APP_DIR))

from shared import config  # noqa: E402


def dashboard_url():
    port = config.get_config("WEB_PORT", 50001)
    scheme = "https" if config.get_config("TLS_CERT") else "http"
    return f"{scheme}://127.0.0.1:{port}/"


def check(url, timeout=4):
    """True when url answers 200. Never through a proxy: it is this machine."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(url, timeout=timeout) as response:
            return response.status == 200
    except OSError as e:
        print(f"{url}: {e}")
        return False


def main(argv):
    config.init(APP_DIR, config.config_file_from_argv(argv), config.data_dir_from_env())
    return 0 if check(dashboard_url()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
