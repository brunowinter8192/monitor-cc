# INFRASTRUCTURE
import os
import signal
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional, Tuple

# From proc_cache.py: Tasks base dir + CC process cache for project attribution
from .proc_cache import _TASKS_BASE, _cc_proc_cache
# From menubar_log.py: unified log sink for abort action events
from .menubar_log import log_menubar

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

# Scan for Opus 'sleep N && echo done' timers; attribute each to a project via ancestry→cwd lookup.
# Walks up to 5 levels of process ancestry to find the CC process in _cc_proc_cache (handles
# intermediate shell layers between CC and the zsh that runs the sleep command).
# cwd_to_project: {session_cwd: project_name} built from list_alive_sessions() mains in caller.
# Returns {project_name: BgSleepInfo}; 'unknown' key for timers whose CC process is unresolvable.
def _scan_bg_sleep_timers(cwd_to_project: Dict[str, str]) -> Dict[str, BgSleepInfo]:
    try:
        r = subprocess.run(
            ['ps', '-A', '-o', 'pid=,ppid=,etime=,args='],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=3)
    except Exception:
        return {}
    pid_info: Dict[str, Tuple[str, str, str]] = {}
    for line in r.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            pid_info[parts[0]] = (parts[1], parts[2], parts[3])
    buckets: Dict[str, List[Tuple[int, int]]] = {}   # project_name → [(remaining, sleep_pid)]
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
        remaining = max(0, int(float(tokens[1])) - elapsed)
        # Walk ancestry chain upward from zsh's parent — handles depth > 2 (intermediate
        # shell layers between CC and zsh). Stops when a CC process is found in the cache.
        ancestor_pid = parent[0]
        for _ in range(5):
            if ancestor_pid in _cc_proc_cache:
                break
            ancestor_info = pid_info.get(ancestor_pid)
            if ancestor_info is None:
                break
            ancestor_pid = ancestor_info[0]
        cc_entry = _cc_proc_cache.get(ancestor_pid)
        cwd = cc_entry[1] if cc_entry else ''
        project_name = cwd_to_project.get(cwd, 'unknown')
        buckets.setdefault(project_name, []).append((remaining, int(pid)))
    return {
        proj: BgSleepInfo(min_remaining=min(e[0] for e in entries),
                          sleep_pids=[e[1] for e in entries])
        for proj, entries in buckets.items()
    }

# Collapse per-project scan result to single Optional[BgSleepInfo] for panel/abort callers
def _aggregate_bg(result: Dict[str, BgSleepInfo]) -> Optional[BgSleepInfo]:
    if not result:
        return None
    return BgSleepInfo(
        min_remaining=min(info.min_remaining for info in result.values()),
        sleep_pids=[p for info in result.values() for p in info.sleep_pids],
    )

# Kill sleep PIDs for Opus background timers; write 'aborted\n' to all 0-byte task files
def _abort_bg_sleep_timers(sleep_pids: List[int]) -> int:
    killed = 0
    errors = 0
    last_err = None
    for pid in sleep_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, OSError) as e:
            errors += 1
            last_err = e
    try:
        ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:23]
        pids_str = ','.join(str(p) for p in sleep_pids)
        err_extra = f' last_err={repr(last_err)}' if last_err else ''
        line = f'{ts} abort_action pids=[{pids_str}] killed={killed} errors={errors}{err_extra}'
        log_menubar('abort', line)
    except Exception as e:
        print(f'[abort-log] abort_action write error: {e}', file=sys.stderr)
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
