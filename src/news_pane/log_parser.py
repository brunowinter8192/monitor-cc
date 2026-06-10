# INFRASTRUCTURE
import re
from pathlib import Path

SEARXNG_ROOT   = Path('/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/searxng-cli')
LOG_DIR        = SEARXNG_ROOT / 'src' / 'logs'
LAST_RUN_FILE  = LOG_DIR / 'news_coindesk_last_run.txt'
TARGET_COLLECTION = 'searxng_crypto'

RUN_START_MARKER = '=== coindesk pipeline started ==='
RUN_END_MARKER   = '=== coindesk pipeline complete ==='

# Log line format: [YYYY-MM-DD HH:MM:SS] LEVEL message
_LOG_LINE_RE = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\w+)\s+(.*)')

_WHITELIST = [
    re.compile(r'Checking preconditions'),
    re.compile(r'  \[(OK|FAIL)\]'),
    re.compile(r'STAGE (?:discover|dedup|scrape|cleanup|publish)'),
    re.compile(r'(?:discover|dedup|scrape|cleanup|publish)\s+→'),
    re.compile(r'Nothing new to scrape'),
    re.compile(r'RegwallGuardError'),
    re.compile(r'=== coindesk pipeline'),
]

# FUNCTIONS

# Return Path to newest news_coindesk_*.log by mtime; None if none found
def find_log_file() -> Path | None:
    candidates = sorted(LOG_DIR.glob('news_coindesk_*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


# Return stripped timestamp string from LAST_RUN_FILE; None if missing or unreadable
def read_last_run_ts() -> str | None:
    try:
        return LAST_RUN_FILE.read_text().strip() or None
    except OSError:
        return None


# Return all lines after the last RUN_START_MARKER in log_path; [] if file unreadable
def find_current_run_lines(log_path: Path) -> list[str]:
    try:
        text = log_path.read_text(errors='replace')
    except OSError:
        return []
    lines = text.splitlines()
    last_start = -1
    for i, line in enumerate(lines):
        if RUN_START_MARKER in line:
            last_start = i
    if last_start < 0:
        return lines
    return lines[last_start:]


# Return lines from current_run_lines that match the whitelist or are WARNING/ERROR level
def filter_events(lines: list[str]) -> list[str]:
    result = []
    for line in lines:
        m = _LOG_LINE_RE.match(line)
        if m:
            level = m.group(2).upper()
            msg   = m.group(3)
            if level in ('WARNING', 'ERROR'):
                result.append(line)
                continue
            if any(pat.search(msg) for pat in _WHITELIST):
                result.append(line)
        else:
            if any(pat.search(line) for pat in _WHITELIST):
                result.append(line)
    return result
