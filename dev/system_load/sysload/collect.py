# INFRASTRUCTURE
import os
import re
import subprocess
import time
from typing import Optional

from sysload.config import (
    SUBPROCESS_TIMEOUT_SECONDS, TASK_OUTPUT_SUFFIX, TASKS_BASE, TOP_SAMPLE_SECONDS, TOP_SAMPLES,
)

_PS_FIELDS = 'pid=,ppid=,uid=,tty=,etime=,cputime=,rss=,stat=,lstart=,command='
_PS_HEAD_TOKENS = 8
_PS_LSTART_TOKENS = 5
_FREE_PCT_RE = re.compile(r'free percentage:\s*(\d+)%')
_SWAP_USED_RE = re.compile(r'used = ([\d.]+)M')


# FUNCTIONS

def run_text(command: list) -> Optional[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=SUBPROCESS_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def run_with_status(command: list) -> tuple:
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=SUBPROCESS_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return None, -1
    return result.stdout, result.returncode


def collect_procs() -> list:
    text = run_text(['ps', '-A', '-ww', '-o', _PS_FIELDS])
    if text is None:
        raise RuntimeError('ps failed, no snapshot possible')
    procs = [parse_ps_line(line) for line in text.splitlines()]
    return [p for p in procs if p is not None]


def parse_ps_line(line: str) -> Optional[dict]:
    parts = line.split(None, _PS_HEAD_TOKENS + _PS_LSTART_TOKENS)
    if len(parts) < _PS_HEAD_TOKENS + _PS_LSTART_TOKENS:
        return None
    pid, ppid, uid, tty, etime, cputime, rss, stat = parts[:_PS_HEAD_TOKENS]
    lstart = ' '.join(parts[_PS_HEAD_TOKENS:_PS_HEAD_TOKENS + _PS_LSTART_TOKENS])
    command = parts[_PS_HEAD_TOKENS + _PS_LSTART_TOKENS] if len(parts) > _PS_HEAD_TOKENS + _PS_LSTART_TOKENS else ''
    return {
        'pid': int(pid), 'ppid': int(ppid), 'uid': int(uid), 'tty': tty,
        'age_s': parse_clock(etime), 'cpu_s': parse_clock(cputime),
        'rss_kb': int(rss), 'stat': stat, 'lstart': lstart, 'command': command.strip(),
    }


def parse_clock(value: str) -> float:
    days = 0
    if '-' in value:
        day_part, value = value.split('-', 1)
        days = int(day_part)
    parts = [float(p) for p in value.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def collect_cpu_now() -> dict:
    text = run_text(['top', '-l', str(TOP_SAMPLES), '-s', str(TOP_SAMPLE_SECONDS), '-stats', 'pid,cpu'])
    if text is None:
        return {}
    return parse_top_last_sample(text)


def parse_top_last_sample(text: str) -> dict:
    lines = text.splitlines()
    header_indexes = [i for i, line in enumerate(lines) if line.split()[:1] == ['PID']]
    if not header_indexes:
        return {}
    cpu_now = {}
    for line in lines[header_indexes[-1] + 1:]:
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit():
            cpu_now[int(fields[0])] = float(fields[1])
    return cpu_now


def collect_tmux() -> dict:
    sessions_text, sessions_rc = run_with_status(['tmux', 'list-sessions', '-F', '#{session_name}|#{session_created}'])
    panes_text, panes_rc = run_with_status(['tmux', 'list-panes', '-a', '-F', '#{session_name}|#{pane_pid}|#{pane_current_path}'])
    if sessions_rc != 0 or panes_rc != 0:
        return {'ok': False, 'sessions': [], 'panes': []}
    return {'ok': True, 'sessions': parse_tmux_sessions(sessions_text), 'panes': parse_tmux_panes(panes_text)}


def parse_tmux_sessions(text: str) -> list:
    sessions = []
    for line in text.splitlines():
        name, _, created = line.partition('|')
        if name and created.strip().isdigit():
            sessions.append({'name': name, 'created': int(created)})
    return sessions


def parse_tmux_panes(text: str) -> list:
    panes = []
    for line in text.splitlines():
        parts = line.split('|', 2)
        if len(parts) == 3 and parts[1].isdigit():
            panes.append({'session': parts[0], 'pane_pid': int(parts[1]), 'path': parts[2]})
    return panes


def collect_task_files(now: float) -> list:
    if not TASKS_BASE.exists():
        return []
    text = run_text(['lsof', '+D', str(TASKS_BASE), '-Fpn'])
    if text is None:
        return []
    files = []
    for pid, path in parse_lsof_pairs(text):
        if not path.endswith(TASK_OUTPUT_SUFFIX):
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        files.append({'pid': pid, 'path': path, 'size': stat.st_size, 'mtime_age_s': round(now - stat.st_mtime, 1)})
    return files


def parse_lsof_pairs(text: str) -> list:
    pairs, current = [], None
    for line in text.splitlines():
        if line.startswith('p') and line[1:].isdigit():
            current = int(line[1:])
        elif line.startswith('n') and current is not None:
            pairs.append((current, line[1:]))
    return pairs


def collect_established() -> Optional[list]:
    text = run_text(['lsof', '-nP', '-iTCP', '-sTCP:ESTABLISHED', '-Fn'])
    if text is None:
        return None
    return [line[1:] for line in text.splitlines() if line.startswith('n')]


def collect_cwds(pids: list) -> dict:
    if not pids:
        return {}
    text = run_text(['lsof', '-a', '-d', 'cwd', '-p', ','.join(str(p) for p in pids), '-Fpn'])
    if text is None:
        return {}
    return {pid: path for pid, path in parse_lsof_pairs(text)}


def collect_system() -> dict:
    load = os.getloadavg()
    pressure = run_text(['memory_pressure']) or ''
    swap = run_text(['sysctl', '-n', 'vm.swapusage']) or ''
    free = _FREE_PCT_RE.search(pressure)
    used = _SWAP_USED_RE.search(swap)
    return {
        'load': [round(x, 2) for x in load],
        'mem_free_pct': int(free.group(1)) if free else None,
        'swap_used_mb': float(used.group(1)) if used else None,
        'ncpu': os.cpu_count(),
    }


def read_own_identity() -> dict:
    return {'self_pid': os.getpid(), 'uid': os.getuid(), 'taken_at': time.time()}
