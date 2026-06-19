# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_gh_cli_chained.py"

CASES = [
    # (description, command, expected_exit_code)
    # --- true positives: must block ---
    ("search_repos piped to grep BLOCK",
     "gh-cli search_repos \"foo\" | grep bar", 2),
    ("search_code piped to head BLOCK",
     "gh-cli search_code \"x\" owner/repo | head -10", 2),
    ("get_repo_tree piped to tail BLOCK",
     "gh-cli get_repo_tree owner/repo | tail -5", 2),
    ("get_file_content piped to sed BLOCK",
     "gh-cli get_file_content owner/repo path | sed 's/x/y/'", 2),
    ("index_issues piped to grep BLOCK",
     "gh-cli index_issues \"q\" o/r | grep open", 2),
    ("index_discussions piped to wc BLOCK",
     "gh-cli index_discussions \"q\" o/r | wc -l", 2),
    ("index_releases piped to awk BLOCK",
     "gh-cli index_releases o/r | awk '{print}'", 2),
    ("index_issues chained with rag-cli BLOCK",
     "gh-cli index_issues \"q\" o/r && rag-cli index docs", 2),
    ("search_repos chained with echo BLOCK",
     "gh-cli search_repos \"q\" && echo done", 2),
    # --- allowed: must pass ---
    ("two of the 7 chained with semicolon PASS",
     "gh-cli index_issues \"q\" o/r ; gh-cli index_discussions \"q\" o/r", 0),
    ("two of the 7 chained with && PASS",
     "gh-cli search_repos \"q\" && gh-cli search_code \"q\" owner/repo", 0),
    ("standalone with --limit --offset PASS",
     "gh-cli index_issues \"q\" o/r --limit 30 --offset 0", 0),
    ("standalone with --metadata-only PASS",
     "gh-cli get_file_content o/r path --metadata-only", 0),
    ("redirect to file PASS",
     "gh-cli get_file_content o/r path > /tmp/out.txt", 0),
    # --- exempt issue commands: must pass ---
    ("list_issues piped to grep PASS exempt",
     "gh-cli list_issues o/r | grep open", 0),
    ("get_issue piped to head PASS exempt",
     "gh-cli get_issue 123 o/r | head", 0),
    # --- shell-strip: patterns inside quoted/heredoc regions must pass ---
    ("pattern inside single-quotes PASS shell-stripped",
     "echo 'gh-cli index_issues \"q\" o/r | grep foo'", 0),
    ("pattern inside heredoc body PASS shell-stripped",
     "cat <<'EOF'\ngh-cli search_code \"q\" | grep x\nEOF", 0),
]


# ORCHESTRATOR

def test_block_gh_cli_chained_workflow() -> None:
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
    test_block_gh_cli_chained_workflow()
