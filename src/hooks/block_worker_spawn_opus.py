# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active

# worker-cli spawn with 'opus' anywhere after the spawn subcommand (including as model arg)
_SPAWN_OPUS = re.compile(r'\bworker-cli\s+spawn\b.*\bopus\b', re.DOTALL)

_BLOCK_MESSAGE = (
    "BLOCKED: `worker-cli spawn` with model=opus.\n"
    "Workers are ALWAYS Sonnet, NEVER Opus. Opus context is reserved for orchestration\n"
    "only. Using Opus as a worker burns ~20-40\u00d7 billing per token versus Sonnet and\n"
    "defeats the cross-model verification model (both sides would share the same\n"
    "architecture, eliminating the independent second perspective).\n"
    "\n"
    "Fix: use `sonnet` as the model argument, or omit it (default is sonnet):\n"
    "    worker-cli spawn <name> <prompt_file> <project_path> sonnet\n"
    "    worker-cli spawn <name> <prompt_file> <project_path>       # same as sonnet\n"
    "workers-1.md \u00a7 Worker Model.\n"
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr if command spawns a worker with opus model
def block_worker_spawn_opus_workflow() -> None:
    command = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if _SPAWN_OPUS.search(stripped):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON and return tool_input.command; return None on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return cmd if isinstance(cmd, str) else None
    except Exception:
        return None


if __name__ == "__main__":
    block_worker_spawn_opus_workflow()
