# INFRASTRUCTURE
import glob
import json
import os
import re
import shutil
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_KILL_RE = re.compile(r'\bworker-cli\s+kill\s+([\w.-]+)')

_BLOCK_MESSAGE = (
    "worker '{name}' is working — do not kill a working worker. Not possible.\n"
)

# ORCHESTRATOR

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

def _resolve_worker_cli() -> str:
    found = shutil.which('worker-cli')
    if found:
        return found
    candidates = glob.glob(os.path.expanduser(
        '~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/*/bin/worker-cli'
    ))
    return sorted(candidates)[-1] if candidates else None

def _live_worker_status(name: str) -> str:
    try:
        binary = _resolve_worker_cli()
        if binary is None:
            return ''
        result = subprocess.run(
            [binary, 'status', name],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


if __name__ == "__main__":
    block_worker_kill_while_working_workflow()
