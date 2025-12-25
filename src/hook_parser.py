# INFRASTRUCTURE
import json
import logging
from pathlib import Path
from typing import List, Tuple

# From utils.py: ANSI colors and logging utility
from .utils import RESET, GREEN, YELLOW, BLUE, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_hook = logging.getLogger('hook_parser')
hook_handler = logging.FileHandler('src/logs/11_hook_parsing.log')
hook_handler.setFormatter(log_format)
logger_hook.addHandler(hook_handler)
logger_hook.setLevel(logging.INFO)

HOOK_LOG_FILE = Path("src/logs/hook_outputs.jsonl")

# ORCHESTRATOR
def parse_new_hook_entries(last_position: int) -> Tuple[List[dict], int]:
    if not HOOK_LOG_FILE.exists():
        return [], 0

    new_lines = read_new_lines(last_position)
    new_position = get_current_position()
    entries = parse_lines(new_lines)

    if len(entries) > 0:
        log_tagged(logger_hook, "HOOK_PARSED", GREEN, f"Parsed {len(entries)} hook entries")

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
        except json.JSONDecodeError as e:
            log_tagged(logger_hook, "HOOK_JSON_ERR", YELLOW, f"JSON decode error: {e}")
    return entries

# Filter entries by project path
def filter_by_project(entries: List[dict], project_filter: str) -> List[dict]:
    if not project_filter:
        return entries
    return [e for e in entries if e.get('cwd') == project_filter]
