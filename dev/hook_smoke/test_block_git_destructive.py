# INFRASTRUCTURE
import json
import sys
from case_strands import exit_code_runners, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_git_destructive.py"

CASES = [

    ("FP minimal: git push -u + newline + [ -f file ] PASS",
     "git push -u origin main\n[ -f .env ] && source .env", 0),
    ("FP actual recap: push + echo + file-test across lines PASS",
     "git checkout main && git merge dev && (git push || git push -u origin main)\necho done\n[ -f .rag-docs.json ] && rag-cli update_docs .", 0),

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

    ("git commit --amend BLOCK",
     "git commit --amend", 2),
    ("git commit --amend --no-edit BLOCK",
     "git commit --amend --no-edit", 2),

    ("git commit --no-verify BLOCK",
     "git commit --no-verify -m msg", 2),
    ("git push --no-verify BLOCK",
     "git push --no-verify", 2),

    ("git commit --allow-empty BLOCK",
     "git commit --allow-empty -m msg", 2),

    ("git config write user.email BLOCK",
     "git config user.email x@y.com", 2),
    ("git -C /repo config write BLOCK",
     "git -C /repo config core.autocrlf true", 2),

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

    ("push --force in quoted commit message PASS",
     "git commit -m 'deploy: push --force to staging'", 0),
]


# ORCHESTRATOR

def test_block_git_destructive_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, exit_code_runners(CASES, _run_hook)))


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_git_destructive_workflow()
