# INFRASTRUCTURE
import datetime
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_WINDOW_SECS = 30   # rolling window for frequency count (seconds)
_THRESHOLD   = 3    # polls on same target within window that trigger block

# Matches: ps -p <literal-PID> — process-existence check; captures PID
_PS_P_CHECK = re.compile(r'\bps\s+-p\s+(\d+)')
# Matches: tail log-reading forms — short numeric (-N), long -n (with/without space,
# with/without +offset: -n N, -nN, -n +N, -n+N), and GNU --lines= / --lines N;
# captures file path (not the numeric arg — all numeric variants consumed by the flag arm).
# [^\S\n]+ (space/tab only, no newlines) before file arg prevents next-cmd after newline
# being captured as file. Pipe-context check in _extract_target handles pipe-fed variants.
_TAIL_FILE = re.compile(
    r'\btail\s+'
    r'(?:'
    r'-\d+'                                               # -N  (BSD/POSIX short)
    r'|-n[^\S\n]*\+?\d+'                                  # -n N, -nN, -n +N, -n+N
    r'|--lines(?:=[^\S\n]*\+?\d+|[^\S\n]+\+?\d+)'        # --lines=N  or  --lines N
    r')'
    r'[^\S\n]+(\S+)'
)

_BLOCK_MESSAGE = (
    "polling loop — \u22653 checks on the same ps-p/tail target within 30 s; "
    "use `wait $PID` + single `tail` instead\n"
)

# State file path (env-var overridable for test isolation)
_STATE_FILE = os.environ.get(
    "MONITOR_CC_POLLING_STATE",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'logs', 'polling_state.jsonl',
    ),
)

# ORCHESTRATOR

# Read Bash tool_input from stdin; exit 2 + stderr on ≥THRESHOLD polls to same target in window
def block_polling_loop_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    target = _extract_target(stripped)
    if target is None:
        sys.exit(0)
    count = _record_and_count(session_id or "", target)
    if count >= _THRESHOLD:
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_polling_loop", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
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

# Extract poll target fingerprint from shell-stripped command.
# ps -p <N> → "pid:<N>"; tail (any form) <file> → "file:<path>"; pipe-fed tail → None; no match → None
def _extract_target(stripped: str):
    m = _PS_P_CHECK.search(stripped)
    if m:
        return f"pid:{m.group(1)}"
    m = _TAIL_FILE.search(stripped)
    if m:
        before = stripped[:m.start()].rstrip()
        if before.endswith('|') and not before.endswith('||'):
            return None  # pipe-fed tail — reads stdin, no file target
        return f"file:{m.group(1)}"
    return None

# Append new poll entry, prune old entries (self-pruning), return count for (session_id, target).
# Known limitation: concurrent sessions writing simultaneously may lose an entry (one overwrites
# the other's append). This can only cause under-counting (fewer blocks), never over-counting.
# Acceptable since per-session keying means session A's count is unaffected by session B's polls,
# and the system is designed fail-open. No lock needed.
def _record_and_count(session_id: str, target: str) -> int:
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=_WINDOW_SECS)
        entries = _read_recent_entries(cutoff)
        new_entry = {
            'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'session_id': session_id,
            'target': target,
        }
        entries.append(new_entry)
        _write_entries(entries)
        return sum(
            1 for e in entries
            if e.get('session_id') == session_id and e.get('target') == target
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
    block_polling_loop_workflow()
