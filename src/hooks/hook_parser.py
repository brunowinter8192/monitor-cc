# INFRASTRUCTURE
import json
from pathlib import Path
from typing import List, Tuple

HOOK_LOG_FILE = Path("src/logs/hook_outputs.jsonl")

# ORCHESTRATOR
def parse_new_hook_entries(last_position: int) -> Tuple[List[dict], int]:
    if not HOOK_LOG_FILE.exists():
        return [], 0

    new_lines = read_new_lines(last_position)
    new_position = get_current_position()
    entries = parse_lines(new_lines)

    return entries, new_position

# FUNCTIONS

# Read new lines from hook log file
def read_new_lines(last_position: int) -> List[str]:
    with open(HOOK_LOG_FILE, 'r', encoding='utf-8') as f:
        f.seek(last_position)
        content = f.read()
        if not content:
            return []
        lines = content.split('\n')
        if lines and not lines[-1]:
            lines = lines[:-1]
        return lines

# Get current file position
def get_current_position() -> int:
    if not HOOK_LOG_FILE.exists():
        return 0
    return HOOK_LOG_FILE.stat().st_size

# Parse lines into entry dictionaries
def parse_lines(lines: List[str]) -> List[dict]:
    entries = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
        except json.JSONDecodeError:
            pass
    return entries

# Filter entries by project path — prefix match includes worktree subdirectories
def filter_by_project(entries: List[dict], project_filter: str) -> List[dict]:
    if not project_filter:
        return entries
    return [e for e in entries if e.get('cwd', '').startswith(project_filter)]

# Filter entries to only those at or after a given ISO 8601 timestamp
def filter_by_timestamp(entries: List[dict], since_ts: str) -> List[dict]:
    if not since_ts:
        return entries
    return [e for e in entries if e.get('timestamp', '') >= since_ts]
