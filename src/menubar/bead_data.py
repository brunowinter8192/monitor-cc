# INFRASTRUCTURE
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_BD         = '/opt/homebrew/bin/bd'
_BD_TIMEOUT = 5

# FUNCTIONS

# Build {project_name: db_path} from session CWDs; skips projects without .beads/dolt
def project_db_map(sessions) -> Dict[str, Path]:
    seen: Dict[str, Path] = {}
    for s in sessions:
        if not s.cwd or s.project_name in seen:
            continue
        root = _project_root(s.cwd)
        db   = root / '.beads' / 'dolt'
        if db.exists():
            seen[s.project_name] = db
    return seen

# Load all tracked beads per project; returns {project_name: [bead_dict, ...]}
def load_tracked_beads(pdb_map: Dict[str, Path]) -> Dict[str, List[dict]]:
    result: Dict[str, List[dict]] = {}
    for project_name, db_path in pdb_map.items():
        beads = _bd_list_tracked(db_path)
        result[project_name] = beads if beads is not None else []
    return result

# Run bd show --json; returns formatted expand text (description, sources, comments)
def bd_show_text(bead_id: str, db_path: Path) -> str:
    try:
        r = subprocess.run(
            [_BD, 'show', bead_id, '--json', '--db', str(db_path)],
            capture_output=True, text=True, timeout=_BD_TIMEOUT)
        if r.returncode != 0:
            return f'[error: {r.stderr.strip()[:60]}]'
        data  = json.loads(r.stdout)
        bead  = data[0] if isinstance(data, list) and data else data
        if not isinstance(bead, dict):
            return '[no data]'
        return _format_expand_text(bead, bead_id, db_path)
    except Exception as e:
        return f'[error: {e}]'

# Remove 'tracked' label; logs to stderr on failure
def bd_label_remove(bead_id: str, db_path: Path) -> None:
    try:
        subprocess.run(
            [_BD, 'label', 'remove', bead_id, 'tracked', '--db', str(db_path)],
            capture_output=True, timeout=_BD_TIMEOUT)
    except Exception as e:
        import sys
        print(f'bead_data: label remove failed: {e}', file=sys.stderr)

# Derive project root from a session CWD (strip worktree suffix if present)
def _project_root(cwd: str) -> Path:
    if '/.claude/worktrees/' in cwd:
        return Path(cwd.split('/.claude/worktrees/')[0])
    return Path(cwd)

# Run bd list -l tracked --json --db <path>; returns list of bead dicts or None on error
def _bd_list_tracked(db_path: Path) -> Optional[List[dict]]:
    try:
        r = subprocess.run(
            [_BD, 'list', '-l', 'tracked', '--json', '--db', str(db_path)],
            capture_output=True, text=True, timeout=_BD_TIMEOUT)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        return data if isinstance(data, list) else []
    except Exception:
        return None   # distinguish subprocess/parse failure from empty list

# Format bead JSON: description body (≤300 chars), Sources block (full), then all comments
def _format_expand_text(bead: dict, bead_id: str, db_path: Path) -> str:
    lines: List[str] = []
    desc = (bead.get('description') or '').strip()
    if desc:
        # Preserve Sources block in full; truncate only the pre-Sources body
        sources_idx = -1
        for marker in ('Sources referencing', 'Sources\n', 'Sources:'):
            idx = desc.find(marker)
            if idx != -1:
                sources_idx = idx
                break
        if sources_idx != -1:
            pre  = desc[:sources_idx].strip()
            post = desc[sources_idx:].strip()
            if len(pre) > 300:
                pre = pre[:300] + '…'
            if pre:
                lines.extend(pre.split('\n'))
            lines.extend(post.split('\n'))
        else:
            truncated = desc if len(desc) <= 300 else desc[:300] + '…'
            lines.extend(truncated.split('\n'))
    if not lines:
        lines = ['(no description)']
    comments = _bd_fetch_comments(bead_id, db_path)
    for c in comments:
        ts     = _format_comment_ts(c.get('created_at', ''))
        author = c.get('author') or 'unknown'
        text   = (c.get('text') or '').strip()
        lines.append(f'[{ts} by {author}]')
        for tl in (text.split('\n') if text else ['(empty)']):
            lines.append(f'  {tl}')
    return '\n'.join(lines)

# Run bd comments <bead_id> --json --db <path>; returns list of comment dicts (empty on any error)
def _bd_fetch_comments(bead_id: str, db_path: Path) -> List[dict]:
    try:
        r = subprocess.run(
            [_BD, 'comments', bead_id, '--json', '--db', str(db_path)],
            capture_output=True, text=True, timeout=_BD_TIMEOUT)
        if r.returncode != 0 or not r.stdout.strip():
            return []
        data = json.loads(r.stdout)
        return data if isinstance(data, list) else []
    except Exception:
        return []

# Parse ISO8601 timestamp (e.g. '2026-05-21T01:44:54Z') → 'YYYY-MM-DD HH:MM'
def _format_comment_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.astimezone(tz=None).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ts[:16] if len(ts) >= 16 else ts
