# INFRASTRUCTURE
import json
from hook_runner import abort_if_failed, run_hook

HOOK = "src/hooks/block_gh_cli_local_path.py"

CASES = [
    ("get_file_content with /Users/... path BLOCK",
     "gh-cli get_file_content owner repo /Users/x/.claude/projects/foo/tool-results/bar.txt", 2),
    ("get_file_content with ~/... path BLOCK",
     "gh-cli get_file_content owner repo ~/foo.py", 2),
    ("download_files with an absolute repo-path positional BLOCK",
     "gh-cli download_files owner repo /Users/x/abs/path.py", 2),
    ("download_files with a ~/... path among multiple positionals BLOCK",
     "gh-cli download_files owner repo src/a.py ~/b.py --dest /tmp/x", 2),
    ("get_file_content local path with --limit flag before it BLOCK",
     "gh-cli get_file_content owner repo --limit 5 /Users/x/foo.py", 2),
    ("get_file_content with repo-relative path PASS",
     "gh-cli get_file_content owner repo src/main.py", 0),
    ("download_files with repo paths + --dest /tmp/x PASS (the trap case)",
     "gh-cli download_files owner repo src/a.py src/b.py --dest /tmp/x", 0),
    ("download_files with --dest before the paths PASS (dest not treated as a path positional)",
     "gh-cli download_files owner repo --dest /tmp/x src/a.py", 0),
    ("get_file_content with --metadata-only flag, repo-relative path PASS",
     "gh-cli get_file_content owner repo src/main.py --metadata-only", 0),
    ("get_repo_tree untouched PASS",
     "gh-cli get_repo_tree owner repo --path /Users/x/foo", 0),
    ("index_issues untouched PASS",
     'gh-cli index_issues "q" owner/repo', 0),
    ("repo_freshness untouched PASS",
     "gh-cli repo_freshness owner repo", 0),
    ("non-gh-cli command untouched PASS",
     "echo hello", 0),
    ("pattern inside single-quotes PASS shell-stripped",
     "echo 'gh-cli get_file_content owner repo /Users/x/foo.py'", 0),
    ("pattern inside heredoc body PASS shell-stripped",
     "cat <<'EOF'\ngh-cli get_file_content owner repo /Users/x/foo.py\nEOF", 0),
]


# ORCHESTRATOR

def test_block_gh_cli_local_path_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
            abort_if_failed(failures)
    print()
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode())
    return result.returncode


if __name__ == "__main__":
    test_block_gh_cli_local_path_workflow()
