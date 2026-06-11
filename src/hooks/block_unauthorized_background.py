# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# canonical allowed background form: sleep N && echo done (optional whitespace/float)
_CANONICAL = re.compile(r'^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$')

# additional whitelist: reddit-cli index_subreddits (long-running RAG-indexer, ~75-100s)
# paired with rewrite_reddit_index_background.py which auto-sets rb=true for this command
_INDEXER_CANONICAL = re.compile(r'\b(reddit-cli|cli\.py)\s+index_subreddits\b')

# additional whitelist: RAG workflow.py index-dir (long-running, embedding-bound — minutes)
# NOT paired with an auto-background rewrite — backgrounding stays an explicit per-call choice
_RAG_INDEXER_CANONICAL = re.compile(r'\bworkflow\.py\s+index-dir\b')

# additional whitelist: long-running capture/news pipelines (worker launches → goes idle).
# pipe_scraper + pipe_theblock.py are paired with rewrite_pipe_background.py (auto-sets rb=true).
# rag-cli index + workflow.py convert are whitelist-only (explicit per-call choice — Opus may
# run these foreground; auto-forcing would override that and reintroduce cascade risk).
_PIPELINE_CANONICAL = re.compile(
    r'\bpipe_scraper\b'
    r'|\bpipe_theblock\.py\b'
    r'|\brag-cli\s+index\b'
    r'|\bworkflow\.py\s+convert\b'
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; silently rewrite run_in_background=true → false for non-canonical commands
def block_unauthorized_background_workflow() -> None:
    command, run_in_background, session_id = _parse_input()
    if not run_in_background:
        sys.exit(0)
    if command is None:
        sys.exit(0)
    if _is_canonical(command):
        sys.exit(0)
    output = _emit_rewrite(command)
    log_fire("block_unauthorized_background", "rewrite", "Bash", command,
             rewritten="run_in_background: true → false", session_id=session_id)
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

# True if command is the canonical background timer OR a whitelisted long-running pipeline
def _is_canonical(command: str) -> bool:
    return bool(
        _CANONICAL.match(command)
        or _INDEXER_CANONICAL.search(command)
        or _RAG_INDEXER_CANONICAL.search(command)
        or _PIPELINE_CANONICAL.search(command)
    )

# Build allow+updatedInput dict flipping run_in_background to false; return it (caller handles print)
def _emit_rewrite(command: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": command,
                "run_in_background": False,
            },
        },
    }


if __name__ == "__main__":
    block_unauthorized_background_workflow()
