# INFRASTRUCTURE
import json
import re
import subprocess
import sys
from pathlib import Path

_BD          = '/opt/homebrew/bin/bd'
_BD_TIMEOUT  = 5
_MAX_WALK    = 5   # directory levels to walk up searching for .beads/dolt

# bd show <id>  OR  bd comments [add] <id>; group 1 = bead_id
# Pattern per Phase A spec — Opus annotation handles "add" disambiguation
_BD_TRACK_RE = re.compile(r'\bbd\s+(?:show|comments\s+(?:add\s+)?)\s+([A-Za-z]\w*-\w+)')
# Cross-project explicit call: skip if --db or --repo flag is present
_HAS_DB_FLAG = re.compile(r'--(?:db|repo)\b')
# Valid bead-id: ProjectName-suffix (alphanumeric + underscore)
_BEAD_ID_RE  = re.compile(r'^[A-Za-z]\w*-\w+$')
# Shell statement separators — split chained calls; NOT pipe (|)
_SEP_RE      = re.compile(r'(?:;|&&|\|\|)')

# ORCHESTRATOR

# Read PostToolUse payload; per-subcommand: label matching bead as 'tracked'
def bead_tracker_hook_workflow() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return   # malformed payload — nothing to act on
    if payload.get('tool_name') != 'Bash':
        return
    cmd = payload.get('tool_input', {}).get('command', '')
    if not cmd:
        return
    cwd = payload.get('cwd', '')
    if not cwd:
        return
    db_path = _find_db_path(Path(cwd))
    if db_path is None:
        return
    for subcmd in _SEP_RE.split(cmd):
        subcmd = subcmd.strip()
        if not subcmd:
            continue   # empty segment (e.g. trailing ;)
        if _HAS_DB_FLAG.search(subcmd):
            continue   # cross-project subcommand — skip
        m = _BD_TRACK_RE.search(subcmd)
        if not m:
            continue
        bead_id = m.group(1)
        if not _BEAD_ID_RE.match(bead_id):
            continue   # false match — validation exits cleanly
        _bd_label_add(bead_id, db_path)

# FUNCTIONS

# Walk up from start_dir to find .beads/dolt; returns Path or None
def _find_db_path(start_dir: Path):
    current = start_dir
    for _ in range(_MAX_WALK):
        candidate = current / '.beads' / 'dolt'
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None

# Add 'tracked' label idempotently; logs to stderr on subprocess failure (async hook)
def _bd_label_add(bead_id: str, db_path: Path) -> None:
    try:
        subprocess.run(
            [_BD, 'label', 'add', bead_id, 'tracked', '--db', str(db_path)],
            capture_output=True, timeout=_BD_TIMEOUT)
    except Exception as e:
        print(f'bead_tracker_hook: label add failed: {e}', file=sys.stderr)


if __name__ == '__main__':
    bead_tracker_hook_workflow()
