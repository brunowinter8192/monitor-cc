# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_gh_cli_read_noise.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: pipe noise inside the get_issue/list_issues segment is stripped ---
    (
        "get_issue | tail -40 — strip",
        'gh-cli get_issue owner repo 36 | tail -40',
        'gh-cli get_issue owner repo 36',
    ),
    (
        "get_issue 2>&1 | tail -40 — 2>&1 preserved, pipe stripped",
        'gh-cli get_issue owner repo 36 2>&1 | tail -40',
        'gh-cli get_issue owner repo 36 2>&1',
    ),
    (
        "list_issues | head — strip",
        'gh-cli list_issues owner repo | head',
        'gh-cli list_issues owner repo',
    ),
    (
        "get_issue | tail ; echo done — strip pipe, keep chain",
        'gh-cli get_issue owner repo 36 | tail ; echo done',
        'gh-cli get_issue owner repo 36 ; echo done',
    ),
    (
        "cd /x && get_issue | tail — strip pipe, keep chain prefix",
        'cd /x && gh-cli get_issue owner repo 36 | tail',
        'cd /x && gh-cli get_issue owner repo 36',
    ),
    # --- critical: redirects are LEGITIMATE — must NOT be stripped ---
    (
        "get_issue > /tmp/x — UNCHANGED (redirect preserved)",
        'gh-cli get_issue owner repo 36 > /tmp/x',
        None,
    ),
    (
        "get_issue >> /tmp/x — UNCHANGED (append redirect preserved)",
        'gh-cli get_issue owner repo 36 >> /tmp/x',
        None,
    ),
    # --- critical: create_issue/update_issue are writes, out of scope ---
    (
        "create_issue | tail — UNCHANGED (not a covered command)",
        "gh-cli create_issue owner repo 'x' | tail",
        None,
    ),
    (
        "update_issue | tail — UNCHANGED (not a covered command)",
        "gh-cli update_issue owner repo 36 'x' | tail",
        None,
    ),
    # --- negative: nothing to strip, hook is no-op ---
    (
        "bare get_issue — no-op",
        'gh-cli get_issue owner repo 36',
        None,
    ),
    (
        "bare list_issues — no-op",
        'gh-cli list_issues owner repo',
        None,
    ),
    # --- critical: quoted send-message — shell-strip blanks the quoted region ---
    (
        'worker-cli send w "run gh-cli get_issue x | tail" — UNCHANGED (quoted)',
        'worker-cli send w "run gh-cli get_issue x | tail"',
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_gh_cli_read_noise_workflow() -> None:
    failures = []
    for desc, cmd, expected_rewrite in CASES:
        exit_code, rewrite = _run_hook(cmd)
        ok = exit_code == 0 and rewrite == expected_rewrite
        status = "OK  " if ok else "FAIL"
        want = repr(expected_rewrite) if expected_rewrite is not None else "None (no output)"
        got  = repr(rewrite) if rewrite is not None else "None (no output)"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           want: {want}")
            print(f"           got:  {got} (exit={exit_code})")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Invoke the hook script as subprocess; feed payload via stdin; return (exit_code, rewritten_command_or_None)
def _run_hook(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        ["python3", HOOK],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
    )
    rewrite = None
    if proc.stdout.strip():
        try:
            out = json.loads(proc.stdout)
            rewrite = out.get("hookSpecificOutput", {}).get("updatedInput", {}).get("command")
        except json.JSONDecodeError:
            pass
    return proc.returncode, rewrite


if __name__ == "__main__":
    test_rewrite_gh_cli_read_noise_workflow()
