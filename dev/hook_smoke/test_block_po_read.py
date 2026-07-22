# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_po_read.py"
PO_PATH = "~/.claude/projects/-Users-x-proj/abc123-session/tool-results/def456.txt"

CASES = [
    # (description, command, expected_exit_code)
    # --- true positives: must block ---
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
    # --- no-ops: must pass ---
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
]


# ORCHESTRATOR

def test_block_po_read_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
    got = _run_hook_raw(b"not valid json{{{")
    desc = "parse-error fail-open PASS"
    expected = 0
    status = "OK  " if got == expected else "FAIL"
    print(f"  [{status}] {desc}: exit={got} (expected {expected})")
    if got != expected:
        failures.append(desc)
    total = len(CASES) + 1
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {total} tests passed.")


# FUNCTIONS

# Run hook with given command string; return exit code
def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    return _run_hook_raw(payload.encode())

# Run hook with raw stdin bytes; return exit code
def _run_hook_raw(stdin_bytes: bytes) -> int:
    result = subprocess.run(
        ["python3", HOOK],
        input=stdin_bytes,
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_po_read_workflow()
