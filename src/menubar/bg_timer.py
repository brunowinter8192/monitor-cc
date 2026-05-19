# INFRASTRUCTURE
import os
import signal
import subprocess
from typing import Dict, List, NamedTuple, Optional, Tuple

# From proc_cache.py: Tasks base dir for in-progress task detection
from .proc_cache import _TASKS_BASE

# ORCHESTRATOR

# Scan for Opus sleep timers and abort them; internal helpers below
# (No single orchestrator function — module exposes two independent public entry points)

# FUNCTIONS

class BgSleepInfo(NamedTuple):
    min_remaining: int        # shortest remaining seconds across all active sleep timers
    sleep_pids:    List[int]  # PIDs of matching sleep child processes

# Parse ps etime field to seconds. Formats: SS, MM:SS, HH:MM:SS, D-HH:MM:SS
def _parse_etime(etime: str) -> Optional[int]:
    try:
        days_str, _, rest = etime.partition('-')
        if not rest:
            rest, days_str = days_str, '0'
        parts = rest.split(':')
        d = int(days_str) * 86400
        weights = (1, 60, 3600)   # SS weight, MM weight, HH weight
        return d + sum(int(v) * w for v, w in zip(reversed(parts), weights))
    except (ValueError, IndexError):
        pass
    return None

# Scan for Opus 'sleep N && echo done' background timers; return BgSleepInfo or None
def _scan_bg_sleep_timers() -> Optional[BgSleepInfo]:
    try:
        r = subprocess.run(
            ['ps', '-A', '-o', 'pid=,ppid=,etime=,args='],
            capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    pid_info: Dict[str, Tuple[str, str, str]] = {}
    for line in r.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            pid_info[parts[0]] = (parts[1], parts[2], parts[3])
    timer_entries = []   # (remaining_secs, sleep_pid)
    for pid, (ppid, etime, args) in pid_info.items():
        tokens = args.strip().split()
        if len(tokens) != 2 or tokens[0] != 'sleep':
            continue
        if not tokens[1].replace('.', '', 1).isdigit():
            continue
        parent = pid_info.get(ppid, ('', '', ''))
        if 'echo done' not in parent[2]:
            continue
        elapsed = _parse_etime(etime)
        if elapsed is None:
            continue
        timer_entries.append((max(0, int(float(tokens[1])) - elapsed), int(pid)))
    if not timer_entries:
        return None
    return BgSleepInfo(
        min_remaining=min(t[0] for t in timer_entries),
        sleep_pids=[t[1] for t in timer_entries],
    )

# Kill sleep PIDs for Opus background timers; write 'aborted\n' to all 0-byte task files
def _abort_bg_sleep_timers(sleep_pids: List[int]) -> int:
    killed = 0
    for pid in sleep_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, OSError):
            pass
    try:
        for encoded_dir in _TASKS_BASE.iterdir():
            if not encoded_dir.is_dir():
                continue
            for session_dir in encoded_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                tasks_dir = session_dir / 'tasks'
                if not tasks_dir.is_dir():
                    continue
                for f in tasks_dir.glob('*.output'):
                    try:
                        if f.stat().st_size == 0:
                            f.write_text('aborted\n')
                    except OSError:
                        pass
    except OSError:
        pass
    return killed
