# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_SETTINGS_FILE = Path("~/.claude/settings.json").expanduser()
_HOOK_SCRIPT   = Path(__file__).resolve().parent / "block_dangerous_kill.py"
_HOOK_COMMAND  = f"python3 {_HOOK_SCRIPT}"
_HOOK_MATCHER  = "Bash"
_HOOK_TIMEOUT  = 5

# ORCHESTRATOR

# Install PreToolUse safety hook into ~/.claude/settings.json; idempotent
def hook_setup_workflow() -> None:
    settings = _load_settings()
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    if _already_installed(pre):
        print("Safety hook already installed — nothing changed.")
        return
    _add_hook(pre)
    _save_settings(settings)
    print(f"Installed PreToolUse/Bash safety hook → {_SETTINGS_FILE}")
    print("Restart Claude Code to activate the new hook.")

# FUNCTIONS

# True if a hook entry with _HOOK_COMMAND already exists under PreToolUse
def _already_installed(pre_tool_use: list) -> bool:
    for group in pre_tool_use:
        for h in group.get("hooks", []):
            if h.get("command") == _HOOK_COMMAND:
                return True
    return False

# Append a new Bash matcher group to the PreToolUse list
def _add_hook(pre_tool_use: list) -> None:
    pre_tool_use.append({
        "matcher": _HOOK_MATCHER,
        "hooks": [{"type": "command", "command": _HOOK_COMMAND, "timeout": _HOOK_TIMEOUT}],
    })

# Read settings.json; return empty dict if absent; exit on parse error
def _load_settings() -> dict:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

# Atomically write settings back via temp file
def _save_settings(settings: dict) -> None:
    tmp = _SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, _SETTINGS_FILE)


if __name__ == "__main__":
    hook_setup_workflow()
