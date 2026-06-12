# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_worker_cli_response_noise.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: noise inside the response segment is stripped ---
    (
        "| head -20 — strip",
        'worker-cli response X | head -20',
        'worker-cli response X',
    ),
    (
        "| tail -50 — strip",
        'worker-cli response X | tail -50',
        'worker-cli response X',
    ),
    (
        "| grep foo — strip (filters the result)",
        'worker-cli response X | grep foo',
        'worker-cli response X',
    ),
    (
        "> /tmp/r.md redirect — strip",
        'worker-cli response X > /tmp/r.md',
        'worker-cli response X',
    ),
    (
        "2>&1 alone — strip",
        'worker-cli response X 2>&1',
        'worker-cli response X',
    ),
    (
        "2>&1 | head — strip both",
        'worker-cli response X 2>&1 | head',
        'worker-cli response X',
    ),
    (
        "cd /path && worker-cli response X | head — strip pipe, keep cd chain",
        'cd /path && worker-cli response X | head',
        'cd /path && worker-cli response X',
    ),
    (
        "worker-cli response X | head ; bd list — strip pipe, keep trailing chain",
        'worker-cli response X | head ; bd list',
        'worker-cli response X ; bd list',
    ),
    (
        "worker-cli response X | head || echo fail — strip pipe, keep || chain",
        'worker-cli response X | head || echo fail',
        'worker-cli response X || echo fail',
    ),
    # --- negative: nothing to strip, hook is no-op ---
    (
        "bare worker-cli response — no-op",
        'worker-cli response X',
        None,
    ),
    (
        "worker-cli capture X | tail -40 — MUST NOT strip (capture is out of scope)",
        'worker-cli capture X | tail -40',
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
        "cd /path && worker-cli response X bare — no-op (chain, no noise)",
        'cd /path && worker-cli response X',
        None,
    ),
    (
        "worker-cli response X ; bd list — no-op (trailing chain, no pipe)",
        'worker-cli response X ; bd list',
        None,
    ),
    (
        "worker-cli response inside quoted echo — no-op (token in string, not active)",
        'echo "worker-cli response foo | head"',
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_worker_cli_response_noise_workflow() -> None:
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
    test_rewrite_worker_cli_response_noise_workflow()
