# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_SETTINGS_FILE  = Path("~/.claude/settings.json").expanduser()
_HOOK_WRITER    = Path(__file__).resolve().parent / "hook_writer.py"
_HOOK_COMMAND   = f"python3 {_HOOK_WRITER}"
_HOOK_TIMEOUT   = 5

# Events → status mapping mirroring hook_writer._WORKING_EVENTS / _IDLE_EVENTS
_HOOK_EVENTS = ["UserPromptSubmit", "Stop", "StopFailure"]

# ORCHESTRATOR

# Install activity-monitor hooks into ~/.claude/settings.json; idempotent
def hook_setup_workflow() -> None:
    settings = _load_settings()
    hooks = settings.setdefault("hooks", {})
    added = []
    for event in _HOOK_EVENTS:
        if _already_installed(hooks, event):
            print(f"  skip {event}: already present")
        else:
            _add_hook(hooks, event)
            added.append(event)
            print(f"  added {event}")
    if not added:
        print("All hooks already installed — nothing changed.")
        return
    _save_settings(settings)
    print(f"Done. Installed {len(added)} hook(s) into {_SETTINGS_FILE}")
    print("Restart Claude Code to activate the new hooks.")

# FUNCTIONS

# True if a hook entry for _HOOK_COMMAND already exists under event
def _already_installed(hooks: dict, event: str) -> bool:
    for group in hooks.get(event, []):
        for h in group.get("hooks", []):
            if h.get("command") == _HOOK_COMMAND:
                return True
    return False

# Append a new hook group for event to the hooks dict
def _add_hook(hooks: dict, event: str) -> None:
    hooks.setdefault(event, []).append({
        "hooks": [{"type": "command", "command": _HOOK_COMMAND,
                   "timeout": _HOOK_TIMEOUT, "async": True}]
    })

# Read settings.json; exit on fatal parse error
def _load_settings() -> dict:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

# Atomically write settings back
def _save_settings(settings: dict) -> None:
    tmp = _SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, _SETTINGS_FILE)


if __name__ == "__main__":
    hook_setup_workflow()
