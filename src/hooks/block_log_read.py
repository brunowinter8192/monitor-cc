# INFRASTRUCTURE
import datetime
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Matches: logread <file> — captures first arg (the file); 2nd arg is an optional line count, not the file
_LOGREAD_RE = re.compile(r'\blogread\s+(\S+)')
# Read tools that consume a .log as INPUT (tee is excluded — it writes to its file arg)
_READ_TOOL_RE = re.compile(
    r'\b(?:tail|cat|head|grep|egrep|fgrep|sed|less|more|awk|tac|nl|zcat)\b'
)
# .log, .log.1, .log.2, .log.gz — the full filename token must contain this suffix
_LOG_FILE_RE = re.compile(r'\S+\.log(?:\.\d+|\.gz)?\b')
# Output redirect targets to strip before checking for .log input args:
# > file, >> file, N> file, N>> file, &> file, &>> file, 2>&1, 1>&2 (no .log in fd-forms)
_REDIRECT_STRIP = re.compile(r'\s*(?:\d?>>?|&>>?)\s*\S+')
# Split command into pipeline/chain segments for per-segment Branch-A/B classification
_SEGMENT_SPLIT = re.compile(r'\s*(?:&&|\|\||\||\n|;)\s*')

_PRUNE_HOURS = 24   # entries older than this pruned from state (dead-session cleanup; NOT a detection window)

# State file path (env-var overridable for test isolation)
_STATE_FILE = os.environ.get(
    "MONITOR_CC_LOGREAD_STATE",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'logs', 'logread_state.jsonl',
    ),
)

_BLOCK_MSG_A = (
    "go idle immediately! stop whatever you do, go idle!\n"
    "You have read this log 3x this session — that is polling. Stop. "
    "The orchestrator reads the process output when it finishes.\n"
)
_BLOCK_MSG_B = (
    "BLOCKED: read .log files only via `logread <file>` — the single sanctioned log reader. "
    "tail/cat/grep/etc. on a .log are disabled to make log-polling impossible. "
    "If you are waiting for a process, go idle.\n"
)


# ORCHESTRATOR

# Read Bash tool_input from stdin; per-segment dispatch:
#   Branch A — logread segment: count cumulative reads per (session, file); exit 2 on 3rd read.
#   Branch B — non-logread segment with read tool on .log input arg: exit 2 immediately.
def block_log_read_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    segments = [s for s in _SEGMENT_SPLIT.split(stripped) if s.strip()]
    # Branch A pass: record all logread segments; cap at 3rd read of same file per session
    for seg in segments:
        m = _LOGREAD_RE.search(seg)
        if m:
            log_file = m.group(1)
            count = _record_and_count(session_id or "", log_file)
            if count >= 3:
                print(_BLOCK_MSG_A, file=sys.stderr, end="")
                log_fire("block_log_read", "block", "Bash", command, reason=_BLOCK_MSG_A, session_id=session_id)
                sys.exit(2)
    # Branch B pass: block non-logread segments that feed a .log to a read tool
    for seg in segments:
        if _LOGREAD_RE.search(seg):
            continue
        if _is_log_read_segment(seg):
            print(_BLOCK_MSG_B, file=sys.stderr, end="")
            log_fire("block_log_read", "block", "Bash", command, reason=_BLOCK_MSG_B, session_id=session_id)
            sys.exit(2)
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error or missing field (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# True when segment has a read tool AND a .log token that is not a redirect output target
def _is_log_read_segment(seg: str) -> bool:
    cleaned = _strip_redirects(seg)
    return bool(_READ_TOOL_RE.search(cleaned) and _LOG_FILE_RE.search(cleaned))

# Strip output redirect targets iteratively: > f, >> f, N> f, N>> f, &> f, &>> f, 2>&1 etc.
def _strip_redirects(seg: str) -> str:
    cleaned = seg
    while True:
        new = _REDIRECT_STRIP.sub(' ', cleaned)
        if new == cleaned:
            break
        cleaned = new
    return cleaned

# Append new logread entry, prune entries older than _PRUNE_HOURS, return cumulative (session_id, file) count
def _record_and_count(session_id: str, log_file: str) -> int:
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=_PRUNE_HOURS)
        entries = _read_recent_entries(cutoff)
        new_entry = {
            'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'session_id': session_id,
            'file': log_file,
        }
        entries.append(new_entry)
        _write_entries(entries)
        return sum(
            1 for e in entries
            if e.get('session_id') == session_id and e.get('file') == log_file
        )
    except Exception:
        return 0

# Read state file entries with ts >= cutoff; returns list of dicts (skips malformed lines)
def _read_recent_entries(cutoff: datetime.datetime) -> list:
    if not os.path.exists(_STATE_FILE):
        return []
    entries = []
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts_raw = entry.get('ts', '')
                    ts = datetime.datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                    if ts >= cutoff:
                        entries.append(entry)
                except Exception:
                    continue
    except Exception:
        return []
    return entries

# Write entries list to state file (atomic overwrite = self-pruning); fail-silent on any error
def _write_entries(entries: list) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        return


if __name__ == "__main__":
    block_log_read_workflow()
