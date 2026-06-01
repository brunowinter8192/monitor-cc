# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK = "src/hooks/block_batch_bd_close.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- ALLOW: single mutation or reads only ---
    ("close single id ALLOW",
     "bd close Monitor_CC-lhf", 0),
    ("close single id with embedded-value reason ALLOW",
     'bd close Monitor_CC-lhf --reason="batch close A B C now"', 0),
    ("update single id with value-taking flag ALLOW",
     "bd update Monitor_CC-lhf --status closed", 0),
    ("create single ALLOW",
     'bd create "some title" --type task', 0),
    ("close + export chain ALLOW",
     "bd close Monitor_CC-lhf && bd export > .beads/issues.jsonl", 0),
    ("close + list + show chain ALLOW",
     "bd close Monitor_CC-lhf; bd list; bd show Monitor_CC-abc", 0),
    ("close no id last-touched ALLOW",
     "bd close", 0),
    ("comments add single ALLOW",
     'bd comments add Monitor_CC-lhf "Source-Inventory: + foo.md"', 0),
    ("bd in quoted string not trigger ALLOW",
     'echo "bd close A B C"', 0),
    ("list read-only ALLOW",
     "bd list -s open", 0),
    ("show show reads-only chain ALLOW",
     "bd show Monitor_CC-a; bd show Monitor_CC-b", 0),
    # GAP-1: no-id id-list mutator = 1 unit (last-touched mutation)
    ("close no-id alone ALLOW",
     "bd close", 0),
    # GAP-2: set-state has non-id positional arg — treated as other-mutator (1 unit)
    ("set-state single ALLOW",
     "bd set-state Monitor_CC-a in-progress", 0),
    # --- BLOCK: more than 1 mutation unit ---
    ("close two ids BLOCK",
     "bd close Monitor_CC-a Monitor_CC-b", 2),
    ("close two sequential BLOCK",
     "bd close Monitor_CC-a; bd close Monitor_CC-b", 2),
    ("done two ids BLOCK",
     "bd done Monitor_CC-a Monitor_CC-b", 2),
    ("update two ids with flag BLOCK",
     "bd update Monitor_CC-a Monitor_CC-b --status closed", 2),
    ("create create sequential BLOCK",
     'bd create "x"; bd create "y"', 2),
    ("close + update chained BLOCK",
     "bd close Monitor_CC-a && bd update Monitor_CC-b --status closed", 2),
    ("close + comments add chained BLOCK",
     'bd close Monitor_CC-a; bd comments add Monitor_CC-b "x"', 2),
    # GAP-1: two no-id closings → 1+1 = 2 units
    ("close no-id + close no-id BLOCK",
     "bd close; bd close", 2),
    # GAP-1: no-id close + update with id → 1+1 = 2 units
    ("close no-id + update single id BLOCK",
     "bd close; bd update Monitor_CC-x --status closed", 2),
    # GAP-2: two set-state invocations → 1+1 = 2 units
    ("set-state + set-state BLOCK",
     "bd set-state Monitor_CC-a x; bd set-state Monitor_CC-b y", 2),
]


# ORCHESTRATOR

def test_block_batch_bd_close_workflow() -> None:
    log_file = _make_temp_log()
    env = dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=log_file)
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd, env)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Run hook with given command string; return exit code
def _run_hook(command: str, env: dict) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
        env=env,
    )
    return result.returncode

# Create temp file for hook_firing.jsonl to avoid polluting real log
def _make_temp_log() -> str:
    fd, path = tempfile.mkstemp(prefix="hook_fire_test_", suffix=".jsonl")
    os.close(fd)
    return path


if __name__ == "__main__":
    test_block_batch_bd_close_workflow()
