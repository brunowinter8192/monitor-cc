"""
Regression suite for src/poread_cli/__main__.py — the poread CLI's own boundary behavior.

Covers: a valid file within the size ceiling prints exactly the marker shape the proxy-side
inject_poread.py parses, with a correct byte count and sha256 prefix; a file over
constants.POREAD_MAX_BYTES is refused before being read into memory (checked via a monkeypatched
open() that fails the test if ever called for the oversize case), exits 1, prints no marker to
stdout; a missing path is refused, exits 1, prints no marker; a directory path is refused (not
silently treated as a 0-byte file); malformed argv (0 or 2+ positional args) exits 2 with a usage
line, independent of any filesystem state.

Run (from project root):
    ./venv/bin/python dev/poread_cli/test_poread_cli.py
"""

# INFRASTRUCTURE

import hashlib
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[1]))

from src.poread_cli.__main__ import main
from src.constants import POREAD_MAX_BYTES, POREAD_HASH_LEN, POREAD_MARKER_PREFIX

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL: {name}  {detail}")


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def test_valid_file_prints_marker():
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"line one\nline two\n"
        f.write(data)
        path = f.name
    try:
        code, out, err = _run([path])
        expected_hash = hashlib.sha256(data).hexdigest()[:POREAD_HASH_LEN]
        abs_path = os.path.realpath(path)
        expected = f'{POREAD_MARKER_PREFIX}path="{abs_path}" bytes="{len(data)}" sha256="{expected_hash}"/>\n'
        check("exit code 0 for a valid file", code == 0, code)
        check("stdout is exactly the marker line, nothing else", out == expected, repr(out))
        check("stderr is empty on success", err == "", repr(err))
    finally:
        os.unlink(path)


def test_oversize_file_refused_without_reading():
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        f.seek(POREAD_MAX_BYTES)
        f.write(b'\0')
        path = f.name
    try:
        import src.poread_cli.__main__ as mod

        def _fail_if_opened(*a, **kw):
            raise AssertionError("poread must not open() an oversize file at all")
        mod.open = _fail_if_opened
        try:
            code, out, err = _run([path])
        finally:
            del mod.open
        check("exit code 1 for an oversize file", code == 1, code)
        check("no marker printed for an oversize file", out == "", repr(out))
        check("stderr names the ceiling and refuses", "over the" in err and str(POREAD_MAX_BYTES) in err, repr(err))
        check("stderr says no truncated/partial export", "truncated" in err or "partial" in err, repr(err))
    finally:
        os.unlink(path)


def test_missing_file_refused():
    missing = "/tmp/poread_cli_test_definitely_missing_12345.txt"
    if os.path.exists(missing):
        os.unlink(missing)
    code, out, err = _run([missing])
    check("exit code 1 for a missing file", code == 1, code)
    check("no marker printed for a missing file", out == "", repr(out))
    check("stderr mentions the path", missing in err or os.path.realpath(missing) in err, repr(err))


def test_directory_refused_not_treated_as_file():
    with tempfile.TemporaryDirectory() as d:
        code, out, err = _run([d])
        check("exit code 1 for a directory path", code == 1, code)
        check("no marker printed for a directory path", out == "", repr(out))
        check("stderr says not a file", "not a file" in err, repr(err))


def test_bad_argv_exits_2():
    code0, out0, err0 = _run([])
    code2, out2, err2 = _run(["a", "b"])
    check("no-args exits 2", code0 == 2, code0)
    check("no-args prints usage, no marker", out0 == "" and "usage" in err0, (out0, err0))
    check("two-args exits 2", code2 == 2, code2)
    check("two-args prints usage, no marker", out2 == "" and "usage" in err2, (out2, err2))


# ORCHESTRATOR

def test_poread_cli_workflow() -> None:
    test_valid_file_prints_marker()
    test_oversize_file_refused_without_reading()
    test_missing_file_refused()
    test_directory_refused_not_treated_as_file()
    test_bad_argv_exits_2()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_poread_cli_workflow()
