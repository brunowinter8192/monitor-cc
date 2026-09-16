# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/block_cli_chained.py"

CASES = [

    ("rag-cli search piped to head BLOCK",
     'rag-cli search "x" coll | head -40', 2),
    ("gh-cli get_file_content (unprotected subcommand) piped BLOCK — rule 1 is universal",
     "gh-cli get_file_content owner repo path.py | head -80", 2),
    ("worker-cli kill (unprotected subcommand) piped BLOCK",
     "worker-cli kill chore-fridge 2>&1 | tail -5", 2),
    ("linkedin piped to head BLOCK",
     "linkedin --help 2>&1 | head -40", 2),
    ("penny-cli piped BLOCK",
     'penny-cli --klasse "X" | head', 2),
    ("duallog expand piped to head BLOCK",
     "duallog expand s 1 --before 0 --after 0 | head -60", 2),
    ("reddit-cli search_subreddits piped BLOCK",
     'reddit-cli search_subreddits "q" | head', 2),
    ("for-loop over get_issue, one iteration piped BLOCK",
     "for n in 5 62; do echo \"#$n\"; gh-cli get_issue o r $n | sed -n '/^---/,$p'; done", 2),

    ("rag-cli search redirect to file BLOCK",
     'rag-cli search "x" coll > /tmp/out.txt', 2),
    ("gh-cli get_issue redirect BLOCK",
     "gh-cli get_issue owner repo 5 > /tmp/out.txt", 2),
    ("gh-cli list_issues 2>&1 alone (no pipe) BLOCK",
     "gh-cli list_issues owner repo 2>&1", 2),
    ("worker-cli capture redirect BLOCK",
     "worker-cli capture janitor > /tmp/out.txt", 2),
    ("websearch scrape_url_chromium redirect BLOCK (2026-09-06: table used to name a "
     "stale, non-existent subcommand `scrape_url` — this exact subcommand text is the "
     "real one, cli.py has carried it for a while)",
     "websearch scrape_url_chromium URL > /tmp/f.md 2>&1", 2),
    ("websearch search_web redirect PASS (deliberately unprotected, real subcommand)",
     'websearch search_web "some query" > /tmp/out.txt', 0),
    ("duallog sessions redirect BLOCK (every subcommand protected)",
     "duallog sessions > /tmp/out.txt", 2),
    ("linkedin get_messages redirect BLOCK (every subcommand protected)",
     "linkedin get_messages --days 3 > /tmp/out.txt", 2),
    ("penny-cli redirect BLOCK (no subcommand, whole invocation protected)",
     'penny-cli --klasse "X" > out.txt', 2),
    ("reddit-cli search_subreddits redirect BLOCK",
     'reddit-cli search_subreddits "q" > /tmp/out.txt', 2),
    ("bare 2> on protected subcommand does NOT count as a redirect PASS",
     "gh-cli list_issues owner repo 2>/dev/null || true", 0),
    ("unprotected rag-cli index redirect stays allowed PASS (no readback)",
     "rag-cli index --collection x > /tmp/log 2>&1", 0),
    ("unprotected worker-cli status redirect stays allowed PASS",
     "worker-cli status janitor > /tmp/status.txt", 0),
    ("unprotected reddit-cli index_subreddits redirect stays allowed PASS",
     "reddit-cli index_subreddits q sub1 sub2 > /tmp/x.log", 0),

    ("the milestone's canonical incident BLOCK",
     "rag-cli update_docs . > /tmp/ragsync.txt 2>&1; tail -12 /tmp/ragsync.txt", 2),
    ("readback via head BLOCK",
     "gh-cli download_files o r a.py > /tmp/dl.log 2>&1; head -20 /tmp/dl.log", 2),
    ("readback via cat BLOCK",
     "worker-cli status janitor > /tmp/s.txt; cat /tmp/s.txt", 2),
    ("readback of a DIFFERENT file PASS (no target match)",
     "rag-cli index --collection x > /tmp/a.log 2>&1; tail -5 /tmp/b.log", 0),
    ("redirect with no same-call readback stays allowed PASS",
     "rag-cli index --collection x > /tmp/a.log 2>&1; git status --short", 0),

    ("interpreter-path websearch scrape_url_chromium redirect BLOCK (the real incident, "
     "verbatim shape)",
     'cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch && '
     './venv/bin/python cli.py scrape_url_chromium "https://example.com" '
     '> /tmp/out.txt 2>&1', 2),
    ("interpreter-path websearch scrape_url_chromium piped BLOCK (rule 1 applies to the "
     "interpreter form too)",
     'cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch && '
     './venv/bin/python cli.py scrape_url_chromium "https://example.com" | head -40', 2),
    ("interpreter-path gh-cli get_issue redirect BLOCK (mechanism generalizes beyond "
     "websearch — different tool, `.venv` not `venv`, absolute path, no leading cd)",
     '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli/.venv/bin/python '
     '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli/cli.py '
     'get_issue owner repo 5 > /tmp/out.txt', 2),
    ("interpreter-path websearch search_web (unprotected subcommand) redirect PASS",
     'cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch && '
     './venv/bin/python cli.py search_web "some query" > /tmp/out.txt', 0),
    ("interpreter-path with NO known project-dir marker PASS (a random project's own "
     "cli.py is not mistaken for one of the 5 policed CLIs)",
     'cd /tmp/some-other-project && ./venv/bin/python cli.py foo > /tmp/out.txt', 0),

    ("mkdir before rag-cli index PASS (no allowlist of chain segments)",
     "mkdir -p x && rag-cli index --collection x", 0),
    ("ls/echo before gh-cli get_issue PASS",
     'ls ~/foo ; echo "=== issue ==="; gh-cli get_issue owner repo 9', 0),
    ("penny-cli chained with && PASS (isolation retired)",
     'echo test && penny-cli --klasse "Basis Trockenware"', 0),
    ("cd guard before rag-cli search PASS (no redirect, no pipe)",
     'cd /tmp && rag-cli search "x" coll', 0),
    ("cross-CLI chain, both protected, no pipe/redirect PASS",
     "gh-cli get_issue o r 5 && worker-cli capture janitor", 0),
    ("for-loop over get_issue with no pipe/redirect PASS",
     'for n in 62 61 59; do echo "=== #$n ==="; gh-cli get_issue o r $n; done', 0),
    ("duallog path-substring FP PASS (not a real duallog invocation)",
     "cat ~/Meta/iterative-dev/skills/iterative-dev-duallog/SKILL.md | grep -n msgs", 0),
    ("worker-cli status/name substring PASS (not a real duallog invocation)",
     "worker-cli status duallog-search-chars; git -C .claude/worktrees/duallog-search-chars log integration..HEAD", 0),
    ("no known CLI at all PASS",
     "ls -la && git status --short", 0),

    ("cwd-resolved interpreter redirect BLOCK (measured bypass 1: no dir name in the "
     "command, cwd is a websearch worktree)",
     'python3 cli.py scrape_url_chromium "https://example.com" > /tmp/out.txt 2>&1', 2,
     '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch/.claude/worktrees/rawlog'),
    ("cwd-resolved interpreter piped BLOCK (measured bypass 2: no dir name in the command, "
     "cwd is the rag-cli directory itself)",
     'python3 cli.py search "x" coll | head -40', 2,
     '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli'),
    ("cwd-resolved: another project's own cli.py PASS (cwd matches none of the 5 known "
     "CLI directories, exactly like the 259 chore-tracker calls this must keep passing)",
     'python3 cli.py list --status open > /tmp/out.txt', 0,
     '/Users/brunowinter2000/Documents/ai/chore-tracker'),
]


# ORCHESTRATOR

def test_block_cli_chained_workflow() -> None:
    failures = []
    for case in CASES:
        desc, cmd, expected = case[0], case[1], case[2]
        cwd = case[3] if len(case) > 3 else None
        got = _run_hook(cmd, cwd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)

    malformed_got = _run_hook_raw(b"not valid json at all")
    status = "OK  " if malformed_got == 0 else "FAIL"
    print(f"  [{status}] malformed stdin payload fails open: exit={malformed_got} (expected 0)")
    if malformed_got != 0:
        failures.append("malformed stdin payload fails open")

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(CASES) + 1} tests passed.")


# FUNCTIONS

def _run_hook(command: str, cwd: str = None) -> int:
    payload_dict = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if cwd is not None:
        payload_dict["cwd"] = cwd
    return _run_hook_raw(json.dumps(payload_dict).encode())


def _run_hook_raw(stdin_bytes: bytes) -> int:
    result = subprocess.run(
        ["python3", HOOK],
        input=stdin_bytes,
        capture_output=True,
    )
    return result.returncode


if __name__ == "__main__":
    test_block_cli_chained_workflow()
