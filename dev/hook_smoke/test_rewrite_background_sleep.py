# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_background_sleep.py"

# (description, command, run_in_background, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: background timer with N ≠ 600 → rewrite to sleep 600 && echo done ---
    (
        "sleep 300 background timer → normalize to 600",
        "sleep 300 && echo done",
        True,
        "sleep 600 && echo done",
    ),
    (
        "sleep 5 background timer → normalize to 600",
        "sleep 5 && echo done",
        True,
        "sleep 600 && echo done",
    ),
    (
        "sleep 1200 background timer → normalize to 600",
        "sleep 1200 && echo done",
        True,
        "sleep 600 && echo done",
    ),
    # --- negative A: foreground (run_in_background=false) → no rewrite ---
    (
        "foreground sleep 300 — no background flag, no rewrite",
        "sleep 300 && echo done",
        False,
        None,
    ),
    # --- negative B: already 600 → no rewrite ---
    (
        "sleep 600 already canonical — no rewrite",
        "sleep 600 && echo done",
        True,
        None,
    ),
    # --- negative C: non-canonical command (not sleep N && echo done form) → no rewrite ---
    (
        "rag-cli background — not canonical form, no rewrite",
        "rag-cli update_docs .",
        True,
        None,
    ),
    # --- negative D: sleep but wrong chain target (not echo done) → no rewrite ---
    (
        "sleep 300 && rag-cli — not echo done form, no rewrite",
        "sleep 300 && rag-cli server list",
        True,
        None,
    ),
    # --- negative E: bare sleep without chain → no rewrite ---
    (
        "sleep 300 alone — no && echo done, no rewrite",
        "sleep 300",
        True,
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_background_sleep_workflow() -> None:
    failures = []
    for desc, cmd, rb, expected_rewrite in CASES:
        exit_code, rewrite = _run_hook(cmd, rb)
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

# Run hook with given command and run_in_background flag; return (exit_code, rewritten_command_or_None)
def _run_hook(command: str, run_in_background: bool):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command, "run_in_background": run_in_background},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    rewrite = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            data   = json.loads(result.stdout)
            rewrite = data["hookSpecificOutput"]["updatedInput"]["command"]
        except (KeyError, json.JSONDecodeError):
            rewrite = None
    return result.returncode, rewrite


if __name__ == "__main__":
    test_rewrite_background_sleep_workflow()
