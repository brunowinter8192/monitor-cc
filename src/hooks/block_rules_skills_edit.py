# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.hooks._fire_log import log_fire

_BLOCKED_TOOLS = ("Edit", "Write")
_SHARED_RULES_DIR = os.path.join(os.path.expanduser("~"), ".claude", "shared-rules") + os.sep
_SKILLS_DIR_NAME = "skills"

_BLOCK_MESSAGE = "BLOCKED: rules and skills are user-owned — put the proposed change in your process-docs; the user applies it.\n"

# ORCHESTRATOR

def block_rules_skills_edit_workflow() -> None:
    tool_name, file_path, session_id = _parse_input()
    if file_path is None:
        sys.exit(0)
    if _is_protected(file_path):
        _block(tool_name, file_path, session_id)
    sys.exit(0)

# FUNCTIONS

def _parse_input():
    try:
        payload = json.loads(sys.stdin.read())
        tool_name = payload.get("tool_name", "")
        file_path = payload.get("tool_input", {}).get("file_path")
        if tool_name not in _BLOCKED_TOOLS or not isinstance(file_path, str):
            return None, None, None
        return tool_name, file_path, payload.get("session_id")
    except Exception as e:
        log_fire("block_rules_skills_edit", "trace", "Write/Edit", "", reason=f"parse error: {type(e).__name__}: {e}")
        return None, None, None

def _is_protected(file_path: str) -> bool:
    expanded = os.path.expanduser(file_path)
    if expanded.startswith(_SHARED_RULES_DIR):
        return True
    return _SKILLS_DIR_NAME in Path(expanded).parts[:-1]

def _block(tool_name: str, file_path: str, session_id) -> None:
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_rules_skills_edit", "block", tool_name, file_path, reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


if __name__ == "__main__":
    block_rules_skills_edit_workflow()
