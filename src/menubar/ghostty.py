# INFRASTRUCTURE
import json
import os
import subprocess
import time
from typing import Dict, List, Optional

from .paths import _APP_SUPPORT
from .proc_cache import _cc_proc_cache, cc_proc_cache_snapshot

_GHOSTTY_TTY_REFRESH_INTERVAL = 10.0
_GHOSTTY_MARKER_PREFIX = '__GHT_'

_ghostty_tty_to_id: Dict[str, str] = {}
_ghostty_tty_last_refresh: float = 0.0
_ghostty_cwd_uuid_last: dict = {}

# ORCHESTRATOR

def _refresh_ghostty_tty_to_id(now: float) -> None:
    global _ghostty_tty_to_id, _ghostty_tty_last_refresh
    if now - _ghostty_tty_last_refresh < _GHOSTTY_TTY_REFRESH_INTERVAL:
        return
    ghostty_pid = _ghostty_pid()
    if not ghostty_pid:
        return
    all_ttys = _ghostty_child_ttys(ghostty_pid)
    for tty in list(_ghostty_tty_to_id):
        if tty not in all_ttys:
            del _ghostty_tty_to_id[tty]
    new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]
    if not new_ttys:
        _ghostty_tty_last_refresh = now
        return
    tty_marker = _write_markers(new_ttys)
    time.sleep(0.12)
    r3 = _query_terminal_names()
    _clear_markers(tty_marker)
    if not r3 or r3.returncode != 0:
        return
    name_to_id: Dict[str, str] = {}
    for line in r3.stdout.strip().split('\n'):
        if '|||' in line:
            tid, _, tname = line.partition('|||')
            name_to_id[tname.strip()] = tid.strip()
    for tty, marker in tty_marker:
        if marker in name_to_id:
            _ghostty_tty_to_id[tty] = name_to_id[marker]
    _ghostty_tty_last_refresh = now

# FUNCTIONS

def _write_markers(new_ttys: List[str]) -> List[tuple]:
    tty_marker: List[tuple] = []
    for tty in new_ttys:
        marker = f'{_GHOSTTY_MARKER_PREFIX}{os.urandom(4).hex()}'
        tty_marker.append((tty, marker))
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(f'\033]2;{marker}\007'.encode())
        except OSError: pass
    return tty_marker

def _query_terminal_names():
    osa = (
        'tell application "Ghostty"\n'
        '  set pairs to {}\n'
        '  repeat with t in every terminal\n'
        '    set end of pairs to (id of t) & "|||" & (name of t)\n'
        '  end repeat\n'
        '  set AppleScript\'s text item delimiters to ASCII character 10\n'
        '  return pairs as text\n'
        'end tell'
    )
    try:
        return subprocess.run(['osascript', '-e', osa],
                              capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=3)
    except Exception:
        return None

def _clear_markers(tty_marker: List[tuple]) -> None:
    for tty, _ in tty_marker:
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(b'\033]2;\007')
        except OSError: pass

def _ghostty_pid() -> Optional[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=2)
        for line in r.stdout.splitlines():
            if 'Ghostty.app/Contents/MacOS' in line:
                pid = line.split(None, 1)[0].strip()
                if pid.isdigit():
                    return pid
        return None
    except Exception:
        return None

def _ghostty_child_ttys(ghostty_pid: str) -> List[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,ppid=,tty='],
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=3)
        ttys = []
        for line in r.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[1] == ghostty_pid and parts[2] != '??':
                ttys.append(parts[2])
        return ttys
    except Exception:
        return []

def _tty_for_cwd(cwd: str) -> Optional[str]:
    for pid, (tty, proc_cwd) in cc_proc_cache_snapshot().items():
        if proc_cwd == cwd:
            return tty
    return None

def get_ghostty_terminal_id(cwd: str) -> Optional[str]:
    tty = _tty_for_cwd(cwd)
    if tty is None:
        return None
    return _ghostty_tty_to_id.get(tty)

def get_ghostty_terminal_id_for_tty(tty: str) -> Optional[str]:
    return _ghostty_tty_to_id.get(tty)

def _write_cwd_uuid_map() -> None:
    global _ghostty_cwd_uuid_last
    mapping: Dict[str, str] = {}
    for _pid, (tty, cwd) in list(_cc_proc_cache.items()):
        if tty and cwd and tty in _ghostty_tty_to_id:
            mapping[cwd] = _ghostty_tty_to_id[tty]
    if mapping == _ghostty_cwd_uuid_last:
        return
    try:
        _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
        dst = _APP_SUPPORT / "ghostty_cwd_uuid.json"
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(mapping), encoding="utf-8")
        os.replace(tmp, dst)
        _ghostty_cwd_uuid_last = mapping
    except Exception:
        return
