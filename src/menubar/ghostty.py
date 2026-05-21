# INFRASTRUCTURE
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

# From proc_cache.py: CC process cache for tty→cwd lookups
from .proc_cache import _cc_proc_cache

# Inline APP_SUPPORT path (can't import paths.py — would create paths→proc_cache→ghostty→paths cycle)
_APP_SUPPORT = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()

_GHOSTTY_TTY_REFRESH_INTERVAL = 10.0   # cooldown between new-TTY probe cycles
_GHOSTTY_MARKER_PREFIX = '__GHT_'      # OSC 2 title marker prefix (not used by CC)

# tty→Ghostty terminal UUID; populated by OSC 2 title-marker probe (incremental)
_ghostty_tty_to_id: Dict[str, str] = {}
_ghostty_tty_last_refresh: float = 0.0
_ghostty_cwd_uuid_last: dict = {}   # previous write state for change-detection

# ORCHESTRATOR

# Probe new Ghostty TTYs via OSC 2 marker + AppleScript; merge into _ghostty_tty_to_id
def _refresh_ghostty_tty_to_id(now: float) -> None:
    global _ghostty_tty_to_id, _ghostty_tty_last_refresh
    if now - _ghostty_tty_last_refresh < _GHOSTTY_TTY_REFRESH_INTERVAL:
        return
    ghostty_pid = _ghostty_pid()
    if not ghostty_pid:
        return
    all_ttys = _ghostty_child_ttys(ghostty_pid)
    # Stale cleanup: remove cache entries for closed Ghostty terminals
    for tty in list(_ghostty_tty_to_id):
        if tty not in all_ttys:
            del _ghostty_tty_to_id[tty]
    # Only probe TTYs not yet mapped — avoids title-flash on already-known terminals
    new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]
    if not new_ttys:
        return  # no probe; timestamp NOT updated so next tick re-checks
    # Write unique OSC 2 marker into each new TTY
    tty_marker: List[tuple] = []
    for tty in new_ttys:
        marker = f'{_GHOSTTY_MARKER_PREFIX}{os.urandom(4).hex()}'
        tty_marker.append((tty, marker))
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(f'\033]2;{marker}\007'.encode())
        except OSError:
            pass
    time.sleep(0.12)
    # Query Ghostty for id|||name pairs (newline-separated)
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
        r3 = subprocess.run(['osascript', '-e', osa],
                            capture_output=True, text=True, timeout=3)
    except Exception:
        r3 = None
    # Cleanup: restore shell-default title on all probed TTYs
    for tty, _ in tty_marker:
        try:
            with open(f'/dev/{tty}', 'wb', buffering=0) as fh:
                fh.write(b'\033]2;\007')
        except OSError:
            pass
    if not r3 or r3.returncode != 0:
        return
    # Parse output and merge new tty→id entries into cache
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

# Return PID string of running Ghostty.app process, or None
def _ghostty_pid() -> Optional[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,command='],
                           capture_output=True, text=True, timeout=2)
        for line in r.stdout.splitlines():
            if 'Ghostty.app/Contents/MacOS' in line:
                pid = line.split(None, 1)[0].strip()
                if pid.isdigit():
                    return pid
        return None
    except Exception:
        return None

# Return TTY names for all direct children of ghostty_pid (one ps call)
def _ghostty_child_ttys(ghostty_pid: str) -> List[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,ppid=,tty='],
                           capture_output=True, text=True, timeout=3)
        ttys = []
        for line in r.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[1] == ghostty_pid and parts[2] != '??':
                ttys.append(parts[2])
        return ttys
    except Exception:
        return []

# Return tty for the CC process with the given cwd; None if not in cache
def _tty_for_cwd(cwd: str) -> Optional[str]:
    for pid, (tty, proc_cwd) in _cc_proc_cache.items():
        if proc_cwd == cwd:
            return tty
    return None

# Return Ghostty terminal UUID for a main CC session's cwd, or None if not mapped
def get_ghostty_terminal_id(cwd: str) -> Optional[str]:
    tty = _tty_for_cwd(cwd)
    if tty is None:
        return None
    return _ghostty_tty_to_id.get(tty)

# Write {cwd: uuid} map to APP_SUPPORT/ghostty_cwd_uuid.json for hook_writer.py delivery use
# Called from discover.py:list_alive_sessions() after both caches are refreshed
# Skips write when mapping unchanged (change-detection via _ghostty_cwd_uuid_last)
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
