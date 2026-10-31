"""Builds launcher/web/launcher.css from tailwind.css with Tailwind's standalone CLI.

    py launcher/build_css.py path/to/tailwindcss.exe

The CLI is one executable from https://github.com/tailwindlabs/tailwindcss/releases
(tailwindcss-windows-x64.exe and so on), no Node needed. The built file is
committed, so running the launcher needs no build. Its first line carries a
hash of the sources, and a test fails when the sources changed without a rebuild.
"""
import hashlib
import os
import subprocess
import sys

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
SOURCES = ("tailwind.css", "index.html", "app.js")
OUTPUT = os.path.join(WEB_DIR, "launcher.css")


def sources_hash(web_dir=WEB_DIR):
    """SHA-256 of the sources, line endings normalized: a windows checkout must hash the same."""
    digest = hashlib.sha256()
    for name in SOURCES:
        with open(os.path.join(web_dir, name), encoding="utf-8") as f:
            digest.update(name.encode("utf-8") + b"\0" + f.read().replace("\r\n", "\n").encode("utf-8") + b"\0")
    return digest.hexdigest()


def header(web_dir=WEB_DIR):
    return f"/* built by launcher/build_css.py from {', '.join(SOURCES)}, sources {sources_hash(web_dir)} */"


def main(argv):
    tailwind = argv[1] if len(argv) > 1 else "tailwindcss"
    if os.path.dirname(tailwind):
        # a path, relative to where the command was typed; the CLI itself runs in web/
        tailwind = os.path.abspath(tailwind)
    built = OUTPUT + ".tmp"
    command = [tailwind, "-i", os.path.join(WEB_DIR, "tailwind.css"), "-o", built, "--minify"]
    try:
        subprocess.run(command, check=True, cwd=WEB_DIR)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"Tailwind failed: {e}\nGive the path to the standalone CLI: py launcher/build_css.py <tailwindcss>")
    with open(built, encoding="utf-8") as f:
        css = f.read()
    os.remove(built)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(header() + "\n" + css.rstrip("\n") + "\n")
    print(f"Wrote {OUTPUT}, {len(css) // 1024} KB")


if __name__ == "__main__":
    main(sys.argv)
