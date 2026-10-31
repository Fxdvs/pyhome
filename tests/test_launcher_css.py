"""launcher/web/launcher.css is committed built; it must be built from the current sources."""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS_DIR))

from launcher import build_css  # noqa: E402


def test_built_css_is_current():
    with open(build_css.OUTPUT, encoding="utf-8") as f:
        first = f.readline().rstrip("\n")
    assert first == build_css.header(), (
        "launcher.css is older than tailwind.css, index.html or app.js. Rebuild it with "
        "py launcher/build_css.py <path to the Tailwind standalone CLI>"
    )


def test_hash_ignores_line_endings(tmp):
    # a windows checkout turns \n into \r\n; the build must still count as current
    for name in build_css.SOURCES:
        with open(os.path.join(build_css.WEB_DIR, name), encoding="utf-8") as f:
            text = f.read()
        with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
    assert build_css.sources_hash(tmp) == build_css.sources_hash()


def test_page_uses_only_local_files():
    # the launcher works offline: no fonts, scripts or styles from the network
    with open(os.path.join(build_css.WEB_DIR, "index.html"), encoding="utf-8") as f:
        page = f.read()
    assert "http://" not in page and "https://" not in page
    assert 'href="launcher.css"' in page and 'src="app.js"' in page
