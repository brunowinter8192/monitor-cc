# INFRASTRUCTURE
import json
import sys
from case_strands import exit_code_runners, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_dangerous_kill.py"

CASES = [
    ("pkill -f pattern BLOCK",
     'pkill -f "workflow.py --mode menubar"', 2),
    ("pkill -f at start BLOCK",
     "pkill -f some_script.py", 2),
    ("pgrep -f pipe kill BLOCK",
     "pgrep -f some_proc | xargs kill", 2),
    ("kill $(pgrep -f X) BLOCK",
     "kill $(pgrep -f myapp)", 2),
    ("ps grep kill chain BLOCK",
     "ps aux | grep myapp | xargs kill", 2),
    ("pkill -f in single-quoted string PASS",
     "echo 'pkill -f pattern is blocked'", 0),
    ("pkill -f in double-quoted string PASS",
     'echo "pkill -f pattern is blocked"', 0),
    ("pkill -f in heredoc body PASS",
     "python3 <<'EOF'\ntest = 'pkill -f myapp'\nEOF", 0),
    ("pkill -f in heredoc unquoted PASS",
     "cat <<EOF\npkill -f example\nEOF", 0),
    ("pkill -x exact name PASS",
     "pkill -x myapp", 0),
    ("pkill no -f PASS",
     "pkill myapp", 0),
    ("kill numeric pid PASS",
     "kill 12345", 0),
    ("kill signal pid PASS",
     "kill -9 12345", 0),
    ("worker-cli kill PASS",
     "worker-cli kill my-worker", 0),
    ("no kill at all PASS",
     "ls -la && git status", 0),
    ("pkill -9 -f dolt sql-server double-quoted PASS",
     'pkill -9 -f "dolt sql-server"', 0),
    ("pkill -f dolt sql-server single-quoted PASS",
     "pkill -f 'dolt sql-server'", 0),
    ("mixed allowlisted + generic pkill -f BLOCK",
     'pkill -9 -f "dolt sql-server"; pkill -f "workflow.py"', 2),
]


# ORCHESTRATOR

def test_block_dangerous_kill_workflow() -> None:
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
    test_block_dangerous_kill_workflow()
