# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_git_destructive.py"

CASES = [
    # (description, command, expected_exit_code)

    # --- FP regression: multi-line commands with git push + later [ -f ... ] must NOT block ---
    ("FP minimal: git push -u + newline + [ -f file ] PASS",
     "git push -u origin main\n[ -f .env ] && source .env", 0),
    ("FP actual recap: push + echo + file-test across lines PASS",
     "git checkout main && git merge dev && (git push || git push -u origin main)\necho done\n[ -f .rag-docs.json ] && rag-cli update_docs .", 0),

    # --- BLOCK: genuine force-push variants ---
    ("git push --force single-line BLOCK",
     "git push --force", 2),
    ("git push --force-with-lease BLOCK",
     "git push --force-with-lease", 2),
    ("git push -f single-line BLOCK",
     "git push -f", 2),
    ("git push origin main --force BLOCK",
     "git push origin main --force", 2),
    ("git -C /repo push -f BLOCK",
     "git -C /repo push -f", 2),

    # --- BLOCK: git commit --amend ---
    ("git commit --amend BLOCK",
     "git commit --amend", 2),
    ("git commit --amend --no-edit BLOCK",
     "git commit --amend --no-edit", 2),

    # --- BLOCK: --no-verify ---
    ("git commit --no-verify BLOCK",
     "git commit --no-verify -m msg", 2),
    ("git push --no-verify BLOCK",
     "git push --no-verify", 2),

    # --- BLOCK: --allow-empty ---
    ("git commit --allow-empty BLOCK",
     "git commit --allow-empty -m msg", 2),

    # --- BLOCK: git config write variants ---
    ("git config write user.email BLOCK",
     "git config user.email x@y.com", 2),
    ("git -C /repo config write BLOCK",
     "git -C /repo config core.autocrlf true", 2),

    # --- ALLOW: safe git ops ---
    ("git push plain PASS",
     "git push", 0),
    ("git push -u origin main single-line PASS",
     "git push -u origin main", 0),
    ("git commit -m normal PASS",
     "git commit -m 'fix: something'", 0),
    ("git config --list read-only PASS",
     "git config --list", 0),
    ("git config --get read-only PASS",
     "git config --get user.email", 0),
    ("git config --show-origin read-only PASS",
     "git config --show-origin", 0),

    # --- ALLOW: force-push phrase inside quoted commit message ---
    ("push --force in quoted commit message PASS",
     "git commit -m 'deploy: push --force to staging'", 0),
]


# ORCHESTRATOR

def test_block_git_destructive_workflow() -> None:
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
    test_block_git_destructive_workflow()
