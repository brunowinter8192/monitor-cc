# INFRASTRUCTURE
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from .proc_cache import _cc_proc_cache
from .menubar_log import log_menubar

# ORCHESTRATOR

# FUNCTIONS

_WORKER_CLI_WAIT_DEFAULT_TIMEOUT = 3300

class BgSleepInfo(NamedTuple):
    min_remaining: int
    sleep_pids:    List[int]

def _parse_etime(etime: str) -> Optional[int]:
    try:
        days_str, _, rest = etime.partition('-')
        if not rest:
            rest, days_str = days_str, '0'
        parts = rest.split(':')
        d = int(days_str) * 86400
        weights = (1, 60, 3600)
        return d + sum(int(v) * w for v, w in zip(reversed(parts), weights))
    except (ValueError, IndexError):
        pass
    return None

def _is_bare_sleep(tokens: List[str]) -> bool:
    return len(tokens) == 2 and tokens[0] == 'sleep' and tokens[1].replace('.', '', 1).isdigit()

def _worker_cli_wait_index(tokens: List[str]) -> Optional[int]:
    for i, tok in enumerate(tokens[:-1]):
        if os.path.basename(tok) == 'worker-cli' and tokens[i + 1] == 'wait':
            return i
    return None

def _parse_wait_timeout(tokens: List[str]) -> Optional[int]:
    for i, tok in enumerate(tokens):
        if tok == '--timeout' and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            return int(tokens[i + 1])
        if tok.startswith('--timeout=') and tok[len('--timeout='):].isdigit():
            return int(tok[len('--timeout='):])
    return None

def _resolve_ancestor_cwd(start_pid: str, pid_info: Dict[str, Tuple[str, str, str]]) -> str:
    ancestor_pid = start_pid
    for _ in range(5):
        if ancestor_pid in _cc_proc_cache:
            break
        ancestor_info = pid_info.get(ancestor_pid)
        if ancestor_info is None:
            break
        ancestor_pid = ancestor_info[0]
    cc_entry = _cc_proc_cache.get(ancestor_pid)
    return cc_entry[1] if cc_entry else ''

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
    buckets: Dict[str, List[Tuple[int, int]]] = {}
    for pid, (ppid, etime, args) in pid_info.items():
        tokens = args.strip().split()
        elapsed = _parse_etime(etime)
        if elapsed is None:
            continue
        wait_idx = _worker_cli_wait_index(tokens)
        if wait_idx is not None:
            timeout = _parse_wait_timeout(tokens[wait_idx + 2:])
            if timeout is None:
                timeout = _WORKER_CLI_WAIT_DEFAULT_TIMEOUT
            remaining = max(0, timeout - elapsed)
            cwd = _resolve_ancestor_cwd(ppid, pid_info)
            project_name = cwd_to_project.get(cwd, 'unknown')
            buckets.setdefault(project_name, []).append((remaining, int(pid)))
            continue
        if not _is_bare_sleep(tokens):
            continue
        parent = pid_info.get(ppid, ('', '', ''))
        if 'echo done' not in parent[2]:
            continue
        remaining = max(0, int(float(tokens[1])) - elapsed)
        cwd = _resolve_ancestor_cwd(parent[0], pid_info)
        project_name = cwd_to_project.get(cwd, 'unknown')
        buckets.setdefault(project_name, []).append((remaining, int(pid)))
    return {
        proj: BgSleepInfo(min_remaining=min(e[0] for e in entries),
                          sleep_pids=[e[1] for e in entries])
        for proj, entries in buckets.items()
    }

def _aggregate_bg(result: Dict[str, BgSleepInfo]) -> Optional[BgSleepInfo]:
    if not result:
        return None
    return BgSleepInfo(
        min_remaining=min(info.min_remaining for info in result.values()),
        sleep_pids=[p for info in result.values() for p in info.sleep_pids],
    )

def _resolve_pid_output_file(pid: int) -> Optional[str]:
    try:
        r = subprocess.run(
            ['lsof', '-p', str(pid), '-a', '-d', '1,2', '-Fn'],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=2)
    except Exception:
        return None
    for line in r.stdout.splitlines():
        if line.startswith('n') and line.endswith('.output'):
            return line[1:]
    return None

def _abort_bg_sleep_timers(sleep_pids: List[int]) -> int:
    killed = 0
    errors = 0
    last_err = None
    stamped: List[str] = []
    for pid in sleep_pids:
        output_file = _resolve_pid_output_file(pid)
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, OSError) as e:
            errors += 1
            last_err = e
            continue
        if output_file is None:
            continue
        try:
            p = Path(output_file)
            if p.is_file() and p.stat().st_size == 0:
                p.write_text('aborted\n')
                stamped.append(output_file)
        except OSError as e:
            print(f'[abort-stamp] write error for {output_file}: {e}', file=sys.stderr)
    try:
        ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:23]
        pids_str = ','.join(str(p) for p in sleep_pids)
        stamped_str = ','.join(stamped) if stamped else '(none)'
        err_extra = f' last_err={repr(last_err)}' if last_err else ''
        line = (f'{ts} abort_action pids=[{pids_str}] killed={killed} errors={errors} '
                f'stamped=[{stamped_str}]{err_extra}')
        log_menubar('abort', line)
    except Exception as e:
        print(f'[abort-log] abort_action write error: {e}', file=sys.stderr)
    return killed
