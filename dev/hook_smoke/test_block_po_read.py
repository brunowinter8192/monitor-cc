# INFRASTRUCTURE
import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from case_strands import exit_code_runners, fail_open_runner, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_po_read.py"
PO_PATH = "~/.claude/projects/-Users-x-proj/abc123-session/tool-results/def456.txt"

_PINNED_MAX_BYTES = 50_000

_FIXTURE_DIR = tempfile.mkdtemp(prefix="block_po_read_smoke_")
atexit.register(shutil.rmtree, _FIXTURE_DIR, True)
_PO_FIXTURE_SUBTREE = os.path.join(_FIXTURE_DIR, ".claude", "projects", "test-proj", "tool-results")
os.makedirs(_PO_FIXTURE_SUBTREE, exist_ok=True)

_AT_BOUNDARY_PATH = os.path.join(_PO_FIXTURE_SUBTREE, "at_boundary.txt")
_OVER_BOUNDARY_PATH = os.path.join(_PO_FIXTURE_SUBTREE, "over_boundary.txt")
Path(_AT_BOUNDARY_PATH).write_bytes(b"x" * _PINNED_MAX_BYTES)
Path(_OVER_BOUNDARY_PATH).write_bytes(b"x" * (_PINNED_MAX_BYTES + 1))

CASES = [
    ("head on PO export BLOCK",
     f"head -50 {PO_PATH}", 2),
    ("tail on PO export BLOCK",
     f"tail -50 {PO_PATH}", 2),
    ("grep on PO export BLOCK",
     f"grep foo {PO_PATH}", 2),
    ("cat on PO export BLOCK",
     f"cat {PO_PATH}", 2),
    ("sed on PO export BLOCK",
     f"sed -n '1,50p' {PO_PATH}", 2),
    ("rg on PO export BLOCK",
     f"rg foo {PO_PATH}", 2),
    ("piped cat-to-head BLOCK",
     f"cat {PO_PATH} | head -20", 2),
    ("split on PO export BLOCK",
     f"split -l 400 {PO_PATH} /tmp/x", 2),
    ("dd on PO export BLOCK",
     f"dd if={PO_PATH} of=/tmp/x", 2),
    ("head on normal file PASS",
     "head -50 /tmp/normal_file.py", 0),
    ("grep on .log file PASS",
     "grep foo /var/log/app.log", 0),
    ("cat on /tmp/foo.txt not under .claude PASS",
     "cat /tmp/foo.txt", 0),
    ("cat on .claude path not ending .txt PASS",
     "cat /Users/x/.claude/settings.json", 0),
    ("redirect-write to PO path not a read PASS",
     f"echo x > {PO_PATH}", 0),
    ("PO path only in quoted string PASS",
     f"echo 'cat {PO_PATH}'", 0),
    ("real PO export AT boundary (50,000B) BLOCK",
     f"cat {_AT_BOUNDARY_PATH}", 2),
    ("real PO export ONE BYTE OVER boundary (50,001B) PASS",
     f"cat {_OVER_BOUNDARY_PATH}", 0),
    ("dd if= on real PO export over boundary PASS (proves if= prefix is stripped before stat)",
     f"dd if={_OVER_BOUNDARY_PATH} of=/tmp/x", 0),
]


# ORCHESTRATOR

def test_block_po_read_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, _all_runners()))


# FUNCTIONS

def _all_runners() -> dict:
    runners = exit_code_runners(CASES, _run_hook)
    runners.update(fail_open_runner("parse-error fail-open PASS", _run_hook_raw, b"not valid json{{{"))
    return runners


def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    return _run_hook_raw(payload.encode())


def _run_hook_raw(stdin_bytes: bytes) -> int:
    result = run_hook(HOOK, stdin_bytes)
    return result.returncode


if __name__ == "__main__":
    test_block_po_read_workflow()
