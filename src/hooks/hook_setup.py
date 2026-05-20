# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

_SETTINGS_FILE = Path("~/.claude/settings.json").expanduser()
_HOOKS_DIR     = Path(__file__).resolve().parent
_HOOK_TIMEOUT  = 5

# Hook scripts to install: (script_filename, PreToolUse matcher)
_HOOK_SCRIPTS = [
    ("block_dangerous_kill.py",          "Bash"),
    ("block_chained_sleep.py",           "Bash"),
    ("block_unauthorized_background.py", "Bash"),
    ("block_broad_grep.py",              "Bash"),
    ("block_noop_edit.py",               "Edit"),
    ("block_read_directory.py",          "Read"),
    ("block_read_oversize.py",           "Read"),
]
_HOOK_ENTRIES = [(f"python3 {_HOOKS_DIR / s}", m) for s, m in _HOOK_SCRIPTS]

# ORCHESTRATOR

# Install PreToolUse safety hooks into ~/.claude/settings.json; idempotent; supports mixed matchers (Bash/Edit/Read)
def hook_setup_workflow() -> None:
    settings = _load_settings()
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    installed = 0
    for command, matcher in _HOOK_ENTRIES:
        if _already_installed(pre, command):
            print(f"Already installed — skipped: {command}")
        else:
            _add_hook(pre, command, matcher)
            installed += 1
    if installed:
        _save_settings(settings)
        print(f"Installed {installed} PreToolUse safety hook(s) → {_SETTINGS_FILE}")
        print("Restart Claude Code to activate the new hook(s).")
    else:
        print("All safety hooks already installed — nothing changed.")

# FUNCTIONS

# True if a hook entry with the given command already exists under PreToolUse
def _already_installed(pre_tool_use: list, command: str) -> bool:
    for group in pre_tool_use:
        for h in group.get("hooks", []):
            if h.get("command") == command:
                return True
    return False

# Append a new matcher group to the PreToolUse list with the given matcher
def _add_hook(pre_tool_use: list, command: str, matcher: str) -> None:
    pre_tool_use.append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command, "timeout": _HOOK_TIMEOUT}],
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
