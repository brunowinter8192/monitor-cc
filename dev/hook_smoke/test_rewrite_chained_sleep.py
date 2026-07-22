# INFRASTRUCTURE
import json
import subprocess
import sys

HOOK = "src/hooks/rewrite_chained_sleep.py"

# (description, command, expected_rewrite_or_None)
# None = no rewrite expected (hook should emit nothing and exit 0)
CASES = [
    # --- positive: trivial-sync echo before sleep → strip ---
    (
        "echo marker then sleep then tmux — strip sleep",
        "echo \"marker\"; sleep 8; tmux display-message -t ccwrap-phase1 -p '#{pane_title}'",
        "echo \"marker\"; tmux display-message -t ccwrap-phase1 -p '#{pane_title}'",
    ),
    (
        "echo X && sleep then bd — strip sleep",
        'echo "X" && sleep 6 && bd comments add --description "impl"',
        'echo "X" && bd comments add --description "impl"',
    ),
    (
        "true guard before sleep then bd — strip sleep",
        "worker-cli kill X || true; sleep 2; bd list -s open",
        "worker-cli kill X || true; bd list -s open",
    ),
    # --- negative: load-bearing cmd_before → no rewrite ---
    (
        "kill before sleep — load-bearing, no strip",
        "kill $PID 2>&1; sleep 3; check_status",
        None,
    ),
    (
        "launchctl before sleep — load-bearing, no strip",
        "launchctl bootout gui/501/com.example; sleep 1; pgrep -f workflow",
        None,
    ),
    # --- negative: sleep inside loop body → no rewrite ---
    (
        "sleep inside for...done loop — no strip",
        "for i in $(seq 1 30); do echo check; sleep 20; done",
        None,
    ),
    # --- negative: sleep-first (canonical or intent) → no rewrite ---
    (
        "canonical sleep N && echo done — no strip",
        "sleep 5 && echo done",
        None,
    ),
    (
        "sleep-first leading timer intent — no strip",
        "sleep 15 && rag-cli server list",
        None,
    ),
    # --- positive: new single-token _TRIVIAL entries ---
    (
        "grep before sleep — strip",
        'grep -n "pattern" file.py; sleep 2; wc -l file.py',
        'grep -n "pattern" file.py; wc -l file.py',
    ),
    (
        "cat before sleep — strip",
        "cat README.md; sleep 1; head -20 DOCS.md",
        "cat README.md; head -20 DOCS.md",
    ),
    (
        "ls before sleep — strip",
        "ls -la; sleep 2; cat DOCS.md",
        "ls -la; cat DOCS.md",
    ),
    (
        "wc before sleep — strip",
        "wc -l src/foo.py; sleep 1; echo done",
        "wc -l src/foo.py; echo done",
    ),
    (
        "head before sleep — strip",
        "head -20 file.py; sleep 1; tail -20 file.py",
        "head -20 file.py; tail -20 file.py",
    ),
    (
        "tail before sleep — strip",
        'tail -20 file.log; sleep 1; grep "ERROR" file.log',
        'tail -20 file.log; grep "ERROR" file.log',
    ),
    (
        "find before sleep — strip",
        'find . -name "*.py"; sleep 2; ls -la',
        'find . -name "*.py"; ls -la',
    ),
    # --- positive: new _TRIVIAL_PAIRS (git) ---
    (
        "git status before sleep — strip",
        "git status; sleep 2; cat DOCS.md",
        "git status; cat DOCS.md",
    ),
    (
        "git log before sleep — strip",
        "git log --oneline -5; sleep 1; cat file.py",
        "git log --oneline -5; cat file.py",
    ),
    (
        "git diff before sleep — strip",
        "git diff HEAD~1; sleep 2; ls",
        "git diff HEAD~1; ls",
    ),
    (
        "git show before sleep — strip",
        "git show HEAD; sleep 1; echo done",
        "git show HEAD; echo done",
    ),
    # --- positive: new _TRIVIAL_PAIRS (rag-cli, worker-cli) ---
    (
        "rag-cli search before sleep — strip",
        'rag-cli search "query" collection; sleep 2; echo done',
        'rag-cli search "query" collection; echo done',
    ),
    (
        "worker-cli status before sleep — strip",
        "worker-cli status foo; sleep 1; cat DOCS.md",
        "worker-cli status foo; cat DOCS.md",
    ),
    (
        "worker-cli list before sleep — strip",
        "worker-cli list; sleep 2; echo done",
        "worker-cli list; echo done",
    ),
    (
        "worker-cli response before sleep — strip",
        "worker-cli response foo; sleep 1; ls -la",
        "worker-cli response foo; ls -la",
    ),
    # --- negative: critical no-strip — load-bearing git subcommands ---
    (
        "git push before sleep — load-bearing, no strip",
        "git push; sleep 5; echo done",
        None,
    ),
    (
        "git pull before sleep — load-bearing, no strip",
        "git pull; sleep 3; ls",
        None,
    ),
    # --- negative: critical no-strip — load-bearing rag-cli/worker-cli subcommands ---
    (
        "rag-cli index before sleep — load-bearing, no strip",
        "rag-cli index --collection x; sleep 2; echo done",
        None,
    ),
    (
        "rag-cli update_docs before sleep — load-bearing, no strip",
        "rag-cli update_docs .; sleep 2; echo done",
        None,
    ),
    (
        "worker-cli send before sleep — load-bearing, no strip",
        "worker-cli send x msg; sleep 5; echo done",
        None,
    ),
    (
        "worker-cli kill before sleep — load-bearing, no strip",
        "worker-cli kill x; sleep 2; echo done",
        None,
    ),
    # --- negative: critical no-strip — background & is not a chain op ---
    (
        "tail -f log backgrounded & sleep — not a chain op, no strip",
        "tail -f log & sleep 5; echo done",
        None,
    ),
    # --- negative: critical no-strip — git -C flag between cmd and subcommand ---
    (
        "git -C <path> status — flag between cmd and subcmd, conservatively no strip",
        "git -C /repo status; sleep 2; cat file.txt",
        None,
    ),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_rewrite_chained_sleep_workflow() -> None:
    failures = []
    for desc, cmd, expected_rewrite in CASES:
        exit_code, rewrite = _run_hook(cmd)
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

# Run hook with given command; return (exit_code, rewritten_command_or_None)
def _run_hook(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result  = subprocess.run(
        ["python3", HOOK],
        input=payload.encode(),
        capture_output=True,
    )
    rewrite = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            data    = json.loads(result.stdout)
            rewrite = data["hookSpecificOutput"]["updatedInput"]["command"]
        except (KeyError, json.JSONDecodeError):
            rewrite = None
    return result.returncode, rewrite


if __name__ == "__main__":
    test_rewrite_chained_sleep_workflow()
