# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.menubar import ghostty, menubar_log, system

ITERATIVE_DEV_ROOT = Path(sys.argv[1])
REPORT = Path(__file__).resolve().parent / 'md' / 'live_viewer_row_click.md'
SESSION = f'vbgclick{os.getpid()}'
VIEWER_BUNDLE = ghostty.GHOSTTY_VIEWER.bundle_id
SETTLE_S = 1.5
WINDOW_WAIT_S = 20.0


# ORCHESTRATOR

def live_viewer_row_click_workflow() -> None:
    menubar_log.MENUBAR_LOG = Path(tempfile.mkdtemp(prefix='live_click_')) / 'menubar.log'
    start_session()
    open_viewer()
    wait_for_viewer_window()
    refresh_mapping()
    before = front_bundle()
    system._focus_worker(SESSION)
    time.sleep(SETTLE_S)
    after = front_bundle()
    focused = viewer_focused_terminal()
    write_report(before, after, focused)
    cleanup()
    print(REPORT.read_text())


# FUNCTIONS

def run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def start_session() -> None:
    run(['tmux', 'new-session', '-d', '-s', SESSION, 'sleep 600'])


def open_viewer() -> None:
    source = f'source "{ITERATIVE_DEV_ROOT}/src/spawn/worker_io.sh"; open_tmux_viewer "{SESSION}"'
    r = run(['bash', '-c', source])
    if r.returncode != 0:
        raise RuntimeError(f'open_tmux_viewer failed rc={r.returncode} stderr={r.stderr}')


def wait_for_viewer_window() -> None:
    deadline = time.monotonic() + WINDOW_WAIT_S
    while time.monotonic() < deadline:
        if system._find_worker_viewer_tty(SESSION):
            return
        time.sleep(0.2)
    raise RuntimeError('viewer client never attached')


def refresh_mapping() -> None:
    ghostty._ghostty_tty_last_refresh = 0.0
    ghostty._refresh_ghostty_tty_to_id(time.time())


def front_bundle() -> str:
    asn = run(['lsappinfo', 'front']).stdout.strip()
    out = run(['lsappinfo', 'info', '-only', 'bundleid', asn]).stdout
    return out.split('=')[-1].strip().strip('"')


def viewer_focused_terminal() -> str:
    script = (f'tell application id "{VIEWER_BUNDLE}" to return id of focused terminal of selected tab of front window')
    return run(['osascript', '-e', script]).stdout.strip()


def write_report(before: str, after: str, focused: str) -> None:
    tty = system._find_worker_viewer_tty(SESSION)
    mapped = ghostty.get_ghostty_terminal_id_for_tty(tty)
    app = ghostty.get_ghostty_app_for_tty(tty)
    lines = [
        f'# live_viewer_row_click.py report ({time.strftime("%Y-%m-%d %H:%M:%S")})',
        '',
        verdict('viewer tty mapped to the viewer app', app is ghostty.GHOSTTY_VIEWER, f'tty={tty} app={app and app.bundle_id}'),
        verdict('viewer tty has a terminal id', bool(mapped), f'id={mapped}'),
        verdict('row click brought the viewer app to the front', after == VIEWER_BUNDLE, f'before={before} after={after}'),
        verdict('viewer window focused terminal is the mapped terminal', bool(mapped) and focused == mapped, f'focused={focused} mapped={mapped}'),
    ]
    REPORT.write_text('\n'.join(lines) + '\n')


def verdict(label: str, ok: bool, detail: str) -> str:
    return f'- {"PASS" if ok else "FAIL"}: {label} ({detail})'


def cleanup() -> None:
    run(['tmux', 'kill-session', '-t', SESSION])
    time.sleep(3)
    run(['pkill', '-f', 'GhosttyViewer.app/Contents/MacOS/'])


live_viewer_row_click_workflow()
