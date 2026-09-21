"""Runs every tests/test_*.py as its own process. Exit code 1 if any failed."""
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    failed = []
    for file in sorted(os.listdir(TESTS_DIR)):
        if not (file.startswith("test_") and file.endswith(".py")):
            continue
        print(f"== {file}")
        result = subprocess.run([sys.executable, os.path.join(TESTS_DIR, file)])
        if result.returncode != 0:
            failed.append(file)

    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("All test files passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
