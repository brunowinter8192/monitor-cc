# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from .session_finder import find_active_sessions
# From hooks_format.py: Build hook display items
from .hooks_format import build_hook_display_item

# FUNCTIONS

# Scan active sessions' tool-results dirs for persisted hook additionalContext files, keyed by toolUseID
def scan_persisted_hook_files(project_filter: Optional[str]) -> Dict[str, tuple]:
    result = {}
    sessions = find_active_sessions(project_filter)
    for session_file in sessions:
        tool_results_dir = Path(session_file).with_suffix('') / "tool-results"
        if not tool_results_dir.exists():
            continue
        for p in sorted(tool_results_dir.glob("hook-*-additionalContext.txt")):
            name = p.name
            if not name.startswith('hook-') or not name.endswith('-additionalContext.txt'):
                continue
            inner = name[len('hook-'):-len('-additionalContext.txt')]
            last_dash = inner.rfind('-')
            if last_dash < 0 or not inner[last_dash + 1:].isdigit():
                continue
            tool_use_id = inner[:last_dash]
            try:
                mtime = p.stat().st_mtime
                content = p.read_text(encoding='utf-8', errors='replace')
                result[tool_use_id] = (content, mtime)
            except OSError:
                pass
    return result

# Enrich hook display items with persisted additionalContext; returns standalone items for toolu_* files
def enrich_with_persisted(items: List[dict], persisted: Dict[str, tuple], session_start_ts: Optional[str] = None) -> List[dict]:
    if not persisted:
        return []
    uuid_remaining = {tid: (content, mtime) for tid, (content, mtime) in persisted.items()
                      if not tid.startswith('toolu_')}
    toolu_entries = {tid: (content, mtime) for tid, (content, mtime) in persisted.items()
                     if tid.startswith('toolu_')}
    for item in items:
        if item.get('type') != 'hook':
            continue
        if item.get('content') or item.get('was_truncated'):
            continue
        if not item.get('detail'):
            continue
        ts_str = item.get('timestamp', '')
        if not ts_str or not uuid_remaining:
            continue
        try:
            hook_dt = datetime.fromisoformat(ts_str.rstrip('Z'))
        except ValueError:
            continue
        closest_tid = min(uuid_remaining.keys(),
                          key=lambda tid: abs((datetime.utcfromtimestamp(uuid_remaining[tid][1]) - hook_dt).total_seconds()))
        closest_mtime = uuid_remaining[closest_tid][1]
        if abs((datetime.utcfromtimestamp(closest_mtime) - hook_dt).total_seconds()) < 60:
            item['content'] = uuid_remaining.pop(closest_tid)[0]
            item['was_truncated'] = True
    extra = []
    for tid, (content, mtime) in toolu_entries.items():
        dt = datetime.utcfromtimestamp(mtime)
        ts = dt.isoformat() + 'Z'
        if session_start_ts and ts < session_start_ts:
            continue
        entry = {
            'timestamp': ts,
            'hook_event': 'additionalContext',
            'hook_script': f'persisted:{tid[:20]}',
            'output': f'toolUseID={tid}',
            'content': content,
        }
        extra.append(build_hook_display_item(entry))
    return extra
