# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_unauthorized_background.py"

# (description, command, run_in_background, expected_rewritten_bg)
# expected_rewritten_bg:
#   None  = hook emits no output (pass-through, command stays background or already foreground)
#   False = hook emits rewrite flipping run_in_background to false (foreground-forced)
CASES = [
    # --- ALLOW: sleep-only forms — must NOT be foreground-forced ---
    ("sleep N && echo done — original canonical ALLOW",
     "sleep 300 && echo done", True, None),
    ("sleep N bare — now exempt ALLOW",
     "sleep 300", True, None),
    ("sleep N with custom echo text (fire-log actual) ALLOW",
     'sleep 45 && echo "bg-ack-probe done"', True, None),
    ("sleep 600 && echo done — normalized form, hook-order independent ALLOW",
     "sleep 600 && echo done", True, None),

    # --- ALLOW: existing pipeline whitelists — must NOT be foreground-forced ---
    ("reddit-cli index_subreddits whitelist ALLOW",
     "reddit-cli index_subreddits", True, None),
    ("workflow.py index-dir whitelist ALLOW",
     "workflow.py index-dir", True, None),

    # --- FORCE: genuine non-sleep background commands — must be foreground-forced ---
    ("./venv/bin/python script.py — non-sleep background FORCE",
     "./venv/bin/python script.py", True, False),
    ("rag-cli update_docs — original triggering incident FORCE",
     "rag-cli update_docs .", True, False),

    # --- PASS: already foreground — hook is no-op ---
    ("./venv/bin/python script.py foreground — no output PASS",
     "./venv/bin/python script.py", False, None),
]


# ORCHESTRATOR

def test_block_unauthorized_background_workflow() -> None:
    failures = []
    for desc, cmd, rb, expected_bg in CASES:
        got_bg = _run_hook(cmd, rb)
        ok = got_bg == expected_bg
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {desc}: rewritten_bg={got_bg!r} (expected {expected_bg!r})")
        if not ok:
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Run hook; return run_in_background value from rewrite output, or None if hook emits no output
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
    if result.returncode == 0 and result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            return data["hookSpecificOutput"]["updatedInput"]["run_in_background"]
        except (KeyError, json.JSONDecodeError):
            pass
    return None


if __name__ == "__main__":
    test_block_unauthorized_background_workflow()
