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

# PostToolUse Bash hook for auto-tracking beads on bd show/comments calls
_BEAD_HOOK_WRITER  = Path(__file__).resolve().parent / "bead_tracker_hook.py"
_BEAD_HOOK_COMMAND = f"python3 {_BEAD_HOOK_WRITER}"

# ORCHESTRATOR

# Install activity-monitor + bead-tracker hooks into ~/.claude/settings.json; idempotent
def hook_setup_workflow() -> None:
    _guard_not_worktree()
    settings = _load_settings()
    swept = _sweep_stale_hooks(settings)
    if swept:
        _save_settings(settings)
    hooks = settings.setdefault("hooks", {})
    added = []
    for event in _HOOK_EVENTS:
        if _already_installed(hooks, event):
            print(f"  skip {event}: already present")
        else:
            _add_hook(hooks, event)
            added.append(event)
            print(f"  added {event}")
    if _already_installed_bead(hooks):
        print("  skip PostToolUse/bead-tracker: already present")
    else:
        _add_bead_hook(hooks)
        added.append("PostToolUse/bead-tracker")
        print("  added PostToolUse/bead-tracker")
    if added:
        _save_settings(settings)
        print(f"Done. Installed {len(added)} hook(s) into {_SETTINGS_FILE}")
        print("Restart Claude Code to activate the new hooks.")
    elif not swept:
        print("All hooks already installed — nothing changed.")

# FUNCTIONS

# Refuse to run if this script is executing from inside a worktree path
def _guard_not_worktree() -> None:
    parts = Path(__file__).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == '.claude' and parts[i + 1] == 'worktrees':
            print(
                f"ERROR: This script must be run from the main repo root, not from a worktree at "
                f"{Path(__file__).resolve()}.\n"
                "Wechsel in den Main-Repo-Root und rufe das Skript dort auf.",
                file=sys.stderr,
            )
            sys.exit(2)

# Remove hook entries whose python3 script path no longer exists; drop now-empty groups
def _sweep_stale_hooks(settings: dict) -> int:
    hooks = settings.get("hooks", {})
    swept = 0
    for event, groups in list(hooks.items()):
        new_groups = []
        for group in groups:
            new_hooks = []
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                if cmd.startswith("python3 "):
                    tokens = cmd.split()
                    if len(tokens) >= 2 and not os.path.exists(tokens[1]):
                        matcher_label = group.get("matcher", "<no matcher>")
                        print(f"Swept stale: {event} [{matcher_label}] {cmd}")
                        swept += 1
                        continue
                new_hooks.append(h)
            if new_hooks:
                new_groups.append({**group, "hooks": new_hooks})
        hooks[event] = new_groups
    if swept:
        print(f"Swept {swept} stale hook(s)")
    else:
        print("Sweep clean — no stale hooks found")
    return swept

# True if a hook entry for _HOOK_COMMAND already exists under event
def _already_installed(hooks: dict, event: str) -> bool:
    for group in hooks.get(event, []):
        for h in group.get("hooks", []):
            if h.get("command") == _HOOK_COMMAND:
                return True
    return False

# True if _BEAD_HOOK_COMMAND already exists in PostToolUse hooks
def _already_installed_bead(hooks: dict) -> bool:
    for group in hooks.get("PostToolUse", []):
        for h in group.get("hooks", []):
            if h.get("command") == _BEAD_HOOK_COMMAND:
                return True
    return False

# Append PostToolUse/Bash bead-tracker hook group
def _add_bead_hook(hooks: dict) -> None:
    hooks.setdefault("PostToolUse", []).append({
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": _BEAD_HOOK_COMMAND,
                   "timeout": _HOOK_TIMEOUT, "async": True}]
    })

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
