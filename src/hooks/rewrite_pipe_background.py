# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Match invocation of a worker-exclusive long-running capture/news pipeline.
# Only the pipelines Opus never runs interactively are auto-backgrounded here —
# rag-cli index / workflow.py convert are deliberately NOT included (Opus may run
# them foreground; forcing background would override that safe choice and risk a
# background-completion abort cascade). Those stay whitelist-only in
# block_unauthorized_background.py (explicit per-call background).
# Examples matched:
#   cd "$SEARXNG" && ./venv/bin/python -m src.crawler.pipe_scraper --url-file ...
#   python dev/news_pipeline/theblock/pipe_theblock.py
_PIPELINE_RE = re.compile(r'\bpipe_scraper\b|\bpipe_theblock\.py\b')


# ORCHESTRATOR

# Read Bash tool_input from stdin; force run_in_background=true for worker pipeline invocations
def rewrite_pipe_background_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if command is None:
        sys.exit(0)
    if run_in_background:
        sys.exit(0)  # already backgrounded, nothing to do
    stripped = _strip_non_shell_active(command)
    if not _PIPELINE_RE.search(stripped):
        sys.exit(0)  # not a worker pipeline command
    output = _emit_rewrite(command)
    log_fire("rewrite_pipe_background", "rewrite", "Bash", command,
             rewritten="run_in_background: false → true (long-running worker pipeline)",
             session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, run_in_background, session_id); (None, False, None) on error (fail-open)
def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input", {})
        cmd = tool_input.get("command")
        bg = tool_input.get("run_in_background", False)
        cmd = cmd if isinstance(cmd, str) else None
        bg = bg if isinstance(bg, bool) else False
        return cmd, bg, payload.get("session_id")
    except Exception:
        return None, False, None


# Build allow+updatedInput dict flipping run_in_background to true; return it (caller handles print)
def _emit_rewrite(command: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": command,
                "run_in_background": True,
            },
        },
    }


if __name__ == "__main__":
    rewrite_pipe_background_workflow()
