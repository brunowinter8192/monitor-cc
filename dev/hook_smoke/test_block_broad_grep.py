# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_broad_grep.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- true positives: must block ---
    ("bare recursive no scope BLOCK",
     "grep -r foo /tmp/", 2),
    ("recursive dot no scope BLOCK",
     "grep -rn pattern .", 2),
    ("recursive tilde dir BLOCK",
     "grep -R pattern ~/Documents/", 2),
    ("piped to tee not head BLOCK",
     "grep -r foo . | tee /tmp/out.log", 2),
    ("piped to wc not head BLOCK",
     "grep -r foo . | wc -l", 2),
    # --- head-bounded exemption: must pass ---
    ("recursive piped to head PASS",
     "grep -r foo /tmp/ | head -3", 0),
    ("recursive piped to head bare PASS",
     "grep -r foo . | head", 0),
    ("recursive piped to head -N PASS",
     "grep -rn pattern src/ | head -20", 0),
    ("recursive with redirect then head PASS",
     "grep -r foo /tmp/ 2>&1 | head -10", 0),
    ("head then further pipe PASS",
     "grep -r foo . | head -5 | grep bar", 0),
    # --- existing exemptions: must pass ---
    ("has --include scope PASS",
     "grep -rn pattern src/ --include='*.py'", 0),
    ("file-targeted extension PASS",
     "grep -rn pattern workflow.py", 0),
    ("non-recursive PASS",
     "grep -n pattern /tmp/file.log", 0),
    ("git grep exempt PASS",
     "git grep -r pattern src/", 0),
    ("grep in single-quoted string PASS",
     "echo 'grep -r foo .'", 0),
    ("grep in heredoc body PASS",
     "cat <<'EOF'\ngrep -r foo .\nEOF", 0),
]


# ORCHESTRATOR

def test_block_broad_grep_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
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
def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_broad_grep_workflow()
