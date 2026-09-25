# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

SETTINGS_FILE = Path("~/.claude/settings.json").expanduser()

# FUNCTIONS

def guard_not_worktree(script_file: str) -> None:
    parts = Path(script_file).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == '.claude' and parts[i + 1] == 'worktrees':
            print(
                f"ERROR: This script must be run from the main repo root, not from a worktree at "
                f"{Path(script_file).resolve()}.\n"
                "Wechsel in den Main-Repo-Root und rufe das Skript dort auf.",
                file=sys.stderr,
            )
            sys.exit(2)

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

def save_settings(settings: dict) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)
