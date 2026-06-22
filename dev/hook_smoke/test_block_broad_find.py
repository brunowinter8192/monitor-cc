# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_broad_find.py"

CASES = [
    # (description, command, expected_exit_code)

    # --- BLOCK: broad roots, no maxdepth, no head ---
    ("real incident: ~/.claude tree BLOCK",
     "find ~/.claude -type d -iname '*searxng*'", 2),
    ("home dir tilde BLOCK",
     "find ~ -name foo", 2),
    ("home dir trailing slash BLOCK",
     "find ~/ -type f", 2),
    ("home via $HOME BLOCK",
     "find $HOME -type f", 2),
    ("filesystem root BLOCK",
     "find / -name bar", 2),
    ("claude subtree: projects subdir BLOCK",
     "find ~/.claude/projects -type d", 2),
    ("multiple roots: one broad BLOCK",
     "find /tmp ~ -name foo", 2),
    ("$HOME subpath: $HOME/.claude BLOCK",
     "find $HOME/.claude -type d", 2),

    # --- PASS: head-bounded ---
    ("real incident + head PASS",
     "find ~/.claude -type d -iname '*searxng*' | head -20", 0),
    ("home + head PASS",
     "find ~ -name foo | head -5", 0),
    ("root + head PASS",
     "find / -name bar | head", 0),

    # --- PASS: -maxdepth present ---
    ("home with maxdepth PASS",
     "find ~ -maxdepth 2 -name foo", 0),
    ("claude root with maxdepth PASS",
     "find ~/.claude -maxdepth 1 -type d", 0),

    # --- PASS: non-broad roots ---
    ("relative src/ dir PASS",
     "find src/ -name '*.py'", 0),
    ("dot root PASS",
     "find . -type f", 0),
    ("specific project path PASS",
     "find /Users/brunowinter2000/Documents/ai/monitor-cc -name '*.py'", 0),

    # --- PASS: quoted/heredoc — no shell-active find ---
    ("find in double-quoted echo PASS",
     'echo "find ~ -name foo"', 0),
    ("find in worker-cli send quoted arg PASS",
     'worker-cli send x "run: find ~/.claude -type d"', 0),

    # --- PASS: word-boundary — must not match substrings ---
    ("mdfind not matched PASS",
     "mdfind -name foo", 0),
]


# ORCHESTRATOR

def test_block_broad_find_workflow() -> None:
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
    test_block_broad_find_workflow()
