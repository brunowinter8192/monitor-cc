# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_worker_cli_capture_noise.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: pipe noise inside the capture segment is stripped ---
    (
        "| tail -40 — strip",
        'worker-cli capture foo | tail -40',
        'worker-cli capture foo',
    ),
    (
        "| grep bar — strip",
        'worker-cli capture foo | grep bar',
        'worker-cli capture foo',
    ),
    (
        "| head -20 | sed ... — strip from first pipe through segment-end",
        'worker-cli capture foo | head -20 | sed s/x/y/',
        'worker-cli capture foo',
    ),
    (
        "cd /x && worker-cli capture foo | tail ; echo done — strip pipe, keep chains",
        'cd /x && worker-cli capture foo | tail ; echo done',
        'cd /x && worker-cli capture foo ; echo done',
    ),
    (
        "| wc -l — strip",
        'worker-cli capture foo | wc -l',
        'worker-cli capture foo',
    ),
    # --- critical: --raw flag must survive (sits before pipe, not in strip range) ---
    (
        "worker-cli capture foo --raw | tail -40 — flag survives, pipe stripped",
        'worker-cli capture foo --raw | tail -40',
        'worker-cli capture foo --raw',
    ),
    # --- critical: redirects are LEGITIMATE for capture — must NOT be stripped ---
    (
        "worker-cli capture foo > /tmp/x.txt — UNCHANGED (redirect preserved)",
        'worker-cli capture foo > /tmp/x.txt',
        None,
    ),
    (
        "worker-cli capture foo >> /tmp/x.txt — UNCHANGED (append redirect preserved)",
        'worker-cli capture foo >> /tmp/x.txt',
        None,
    ),
    (
        "worker-cli capture foo 2>&1 — UNCHANGED (stderr redirect preserved)",
        'worker-cli capture foo 2>&1',
        None,
    ),
    # --- negative: nothing to strip, hook is no-op ---
    (
        "bare worker-cli capture — no-op",
        'worker-cli capture foo',
        None,
    ),
    (
        "worker-cli capture foo --raw — no-op (flag, no pipe)",
        'worker-cli capture foo --raw',
        None,
    ),
    (
        "worker-cli response X | tail -40 — MUST NOT strip (response is out of scope)",
        'worker-cli response X | tail -40',
        None,
    ),
    (
        "worker-cli status X — wrong subcommand, no-op",
        'worker-cli status X',
        None,
    ),
    (
        "worker-cli list — wrong subcommand, no-op",
        'worker-cli list',
        None,
    ),
    (
        "cd /path && worker-cli capture foo bare — no-op (chain, no noise)",
        'cd /path && worker-cli capture foo',
        None,
    ),
    (
        "worker-cli capture foo ; echo done — no-op (trailing chain, no pipe)",
        'worker-cli capture foo ; echo done',
        None,
    ),
    # --- critical: quoted send-message — shell-strip blanks the quoted region ---
    (
        'worker-cli send w "run worker-cli capture foo | tail" — UNCHANGED (quoted)',
        'worker-cli send w "run worker-cli capture foo | tail"',
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_worker_cli_capture_noise_workflow() -> None:
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
    test_rewrite_worker_cli_capture_noise_workflow()
