# INFRASTRUCTURE
import json
import os
import re
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# worker-cli kill with a name token: [\w.-]+ excludes trailing shell metacharacters so
# 'worker-cli kill foo;' / 'worker-cli kill foo && x' capture 'foo', not 'foo;'.
# Known accepted residual: a shell comment carrying the literal kill + a live-working-worker-name
# blocks — same non-comment-stripping class as the whole hook family (none of the existing
# hooks strip shell comments). The double-gate (regex + live status check) makes a comment-FP
# require both the comment text to name a real worker AND that worker to be actively working.
_KILL_RE = re.compile(r'\bworker-cli\s+kill\s+([\w.-]+)')

_BLOCK_MESSAGE = (
    "worker '{name}' is currently working — stop it first "
    "(ESC or: worker-cli send '{name}' 'stop'), wait until idle, then kill.\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command kills a currently-working worker
def block_worker_kill_while_working_workflow() -> None:
    try:
        command, session_id = _parse_command()
        if command is None:
            sys.exit(0)
        block, name = decide(command, _live_worker_status)
        if block:
            msg = _BLOCK_MESSAGE.format(name=name)
            print(msg, file=sys.stderr, end="")
            log_fire("block_worker_kill_while_working", "block", "Bash", command,
                     reason=msg, session_id=session_id)
            sys.exit(2)
    except Exception:
        sys.exit(0)
    sys.exit(0)

# FUNCTIONS

# Pure decision: strip command, find kill-name(s), check each via status_fn.
# Returns (should_block: bool, blocking_name: str | None).
# Blocks iff any captured name returns exactly 'working' as the first whitespace token.
# status_fn exceptions → '' (allow). Testable: real entrypoint wires _live_worker_status;
# smoke tests inject a stub.
def decide(command: str, status_fn) -> tuple:
    stripped = _strip_non_shell_active(command)
    names = _KILL_RE.findall(stripped)
    if not names:
        return False, None
    for name in names:
        try:
            status = status_fn(name)
        except Exception:
            status = ''
        first = status.split()[0] if status.strip() else ''
        if first == 'working':
            return True, name
    return False, None

# Run 'worker-cli status <name>' with 3s timeout; return stdout or '' on any error/non-zero exit
def _live_worker_status(name: str) -> str:
    try:
        result = subprocess.run(
            ['worker-cli', 'status', name],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_worker_kill_while_working_workflow()
