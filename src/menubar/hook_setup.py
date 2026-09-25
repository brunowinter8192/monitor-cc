# INFRASTRUCTURE
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.claude_settings import SETTINGS_FILE, guard_not_worktree, load_settings, save_settings

_HOOK_WRITER    = Path(__file__).resolve().parent / "hook_writer.py"
_HOOK_COMMAND   = f"python3 {_HOOK_WRITER}"
_HOOK_TIMEOUT   = 5

_HOOK_EVENTS = ["UserPromptSubmit", "Stop", "StopFailure"]

# ORCHESTRATOR

def hook_setup_workflow() -> None:
    guard_not_worktree(__file__)
    settings = load_settings()
    swept = _sweep_stale_hooks(settings)
    if swept:
        save_settings(settings)
    added = _install_missing_hooks(settings)
    if added:
        save_settings(settings)
        _report_installed(added)
    elif not swept:
        print("All hooks already installed — nothing changed.")

# FUNCTIONS

def _install_missing_hooks(settings: dict) -> list:
    hooks = settings.setdefault("hooks", {})
    added = []
    for event in _HOOK_EVENTS:
        _install_event(hooks, event, added)
    return added

def _install_event(hooks: dict, event: str, added: list) -> None:
    if _already_installed(hooks, event):
        print(f"  skip {event}: already present")
    else:
        _add_hook(hooks, event)
        added.append(event)
        print(f"  added {event}")

def _report_installed(added: list) -> None:
    print(f"Done. Installed {len(added)} hook(s) into {SETTINGS_FILE}")
    print("Restart Claude Code to activate the new hooks.")

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

def _already_installed(hooks: dict, event: str) -> bool:
    for group in hooks.get(event, []):
        for h in group.get("hooks", []):
            if h.get("command") == _HOOK_COMMAND:
                return True
    return False

def _add_hook(hooks: dict, event: str) -> None:
    hooks.setdefault(event, []).append({
        "hooks": [{"type": "command", "command": _HOOK_COMMAND,
                   "timeout": _HOOK_TIMEOUT, "async": True}]
    })

if __name__ == "__main__":
    hook_setup_workflow()
