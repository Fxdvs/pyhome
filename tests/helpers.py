"""Tiny test runner, the tests need no framework.

Every function called test_* in the calling module runs with a fresh
temporary directory as its only argument. The working directory is restored
after each test, so a test may chdir into its temp dir.
"""
import os
import tempfile
import traceback


def run_tests(namespace):
    """namespace is the calling module's globals(). Returns an exit code."""
    failed = 0
    tests = [(name, f) for name, f in sorted(namespace.items())
             if name.startswith("test_") and callable(f)]

    for name, test in tests:
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                test(tmp)
                print(f"ok    {name}")
            except BaseException:
                failed += 1
                print(f"FAIL  {name}")
                traceback.print_exc()
            finally:
                # windows cannot delete a directory that is the working directory
                os.chdir(cwd)

    print(f"{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0
