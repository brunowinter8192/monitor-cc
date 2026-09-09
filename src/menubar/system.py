# INFRASTRUCTURE
import fcntl
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .ghostty import get_ghostty_terminal_id, get_ghostty_terminal_id_for_tty
from .paths import PID_FILE as _LOCK_PATH, MONITOR_CC_ROOT
from ..tmux_launcher import generate_session_name, check_session_exists, kill_session

_LAUNCHD_LABEL = 'com.brunowinter.monitor-cc-menubar'
_PLIST_PATH = Path(__file__).resolve().parent / f'{_LAUNCHD_LABEL}.plist'

# ORCHESTRATOR

def run() -> None:
    os.environ.setdefault('LSUIElement', '1')
    _lock_fh = _acquire_singleton_lock()
    if _lock_fh is None:
        print('Another menubar instance is already running, exiting.', file=sys.stderr)
        sys.exit(0)
    from .app import CCMenuBarApp
    app = CCMenuBarApp()
    app.run()

# FUNCTIONS

def _acquire_singleton_lock():
    fh = open(_LOCK_PATH, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fcntl.fcntl(fh, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
    fh.write(str(os.getpid()))
    fh.flush()
    return fh

def _focus_session(cwd: str) -> None:
    import datetime
    import time
    from .menubar_log import log_menubar
    _t0 = time.monotonic()
    term_id = get_ghostty_terminal_id(cwd)
    lookup_ms = (time.monotonic() - _t0) * 1000
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if term_id:
        safe_id = term_id.replace('"', '\\"')
        script = (
            'tell application "Ghostty"\n'
            f'  focus terminal id "{safe_id}"\n'
            'end tell'
        )
        label = f'id={term_id}'
    else:
        safe_cwd = cwd.replace('"', '\\"')
        script = (
            'tell application "Ghostty"\n'
            '  try\n'
            f'    focus (first terminal whose working directory is "{safe_cwd}")\n'
            '    return "MATCH"\n'
            '  on error errMsg number errNum\n'
            '    return "MISS:" & errNum & ":" & errMsg\n'
            '  end try\n'
            'end tell'
        )
        label = f'cwd={cwd}'
    _t1 = time.monotonic()
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, timeout=3)
        osascript_ms = (time.monotonic() - _t1) * 1000
        out = r.stdout.decode(errors='replace').strip()
        if r.returncode != 0:
            msg = f'{ts} ERR rc={r.returncode} {label} stderr={r.stderr.decode(errors="replace").strip()} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'
        elif out.startswith('MISS:'):
            msg = f'{ts} MISS {label} reason={out[5:]} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'
        else:
            msg = f'{ts} OK {label} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'
    except subprocess.TimeoutExpired:
        osascript_ms = (time.monotonic() - _t1) * 1000
        msg = f'{ts} TIMEOUT {label} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'
    with open('/tmp/monitor-cc-menubar_focus.log', 'a') as fh:
        fh.write(msg)
    log_menubar('latency', f'focus lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f} {label}')

def _find_worker_viewer_tty(tmux_session_name: str) -> Optional[str]:
    try:
        r = subprocess.run(['ps', '-A', '-o', 'pid=,tty=,args='],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=3)
    except Exception:
        return None
    for line in r.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        _pid, tty, args = parts
        if tty == '??':
            continue
        tokens = args.split()
        if len(tokens) < 3 or tokens[0] != 'tmux' or tokens[1] not in ('attach', 'attach-session'):
            continue
        if '-t' not in tokens:
            continue
        t_idx = tokens.index('-t')
        if t_idx + 1 < len(tokens) and tokens[t_idx + 1] == tmux_session_name:
            return tty
    return None

def _focus_worker(tmux_session_name: str) -> None:
    import time
    from .menubar_log import log_menubar
    _t0 = time.monotonic()
    tty = _find_worker_viewer_tty(tmux_session_name)
    lookup_ms = (time.monotonic() - _t0) * 1000
    if tty is None:
        log_menubar('latency', f'focus_worker session={tmux_session_name} lookup_ms={lookup_ms:.1f} '
                                f'NO-OP reason=no_attach_client')
        return
    term_id = get_ghostty_terminal_id_for_tty(tty)
    if term_id is None:
        log_menubar('latency', f'focus_worker session={tmux_session_name} tty={tty} lookup_ms={lookup_ms:.1f} '
                                f'NO-OP reason=tty_unmapped')
        return
    safe_id = term_id.replace('"', '\\"')
    script = (
        'tell application "Ghostty"\n'
        f'  focus terminal id "{safe_id}"\n'
        'end tell'
    )
    _t1 = time.monotonic()
    try:
        subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=3)
    except subprocess.TimeoutExpired:
        pass
    osascript_ms = (time.monotonic() - _t1) * 1000
    log_menubar('latency', f'focus_worker session={tmux_session_name} lookup_ms={lookup_ms:.1f} '
                            f'osascript_ms={osascript_ms:.1f} id={term_id}')

_PLIST_PATH_KEY_RE = re.compile(
    r'<key>\s*PATH\s*</key>\s*<string>([^<]*)</string>', re.DOTALL)

def _resolve_launch_python3() -> str:
    try:
        content = _PLIST_PATH.read_text(encoding='utf-8')
        m = _PLIST_PATH_KEY_RE.search(content)
        path_value = m.group(1).strip() if m else None
    except Exception:
        path_value = None
    if not path_value:
        path_value = os.environ.get('PATH', '')
    return shutil.which('python3', path=path_value) or 'python3'

def _build_monitor_launch_cmd(root: Path, python3_path: str, cwd: str) -> str:
    return (f'cd {shlex.quote(str(root))} && '
            f'{shlex.quote(python3_path)} workflow.py --project {shlex.quote(cwd)}')

def _applescript_quote(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def _launch_monitor_ghostty_native(shell_cmd: str):
    script = (
        'tell application "Ghostty"\n'
        '  activate\n'
        '  set win to new window\n'
        '  set t to terminal 1 of selected tab of win\n'
        f'  input text {_applescript_quote(shell_cmd + "; exit")} to t\n'
        '  send key "enter" to t\n'
        'end tell'
    )
    return subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=10)

def _launch_monitor(cwd: str) -> None:
    from .menubar_log import log_menubar
    python3_path = _resolve_launch_python3()
    shell_cmd = _build_monitor_launch_cmd(MONITOR_CC_ROOT, python3_path, cwd)
    r = _launch_monitor_ghostty_native(shell_cmd)
    if r.returncode != 0:
        log_menubar('monitor', f'launch FAILED cwd={cwd} rc={r.returncode} '
                                f'stderr={r.stderr.strip()}')
    else:
        log_menubar('monitor', f'launch OK cwd={cwd}')

def _open_or_focus_monitor(cwd: str) -> None:
    if not cwd:
        return
    session_name = generate_session_name(cwd)
    if check_session_exists(session_name):
        kill_session(session_name)
    _launch_monitor(cwd)
