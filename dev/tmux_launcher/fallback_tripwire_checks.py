# INFRASTRUCTURE
import importlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_SOCKET = 'mcfixprobe'
_REAL_TMUX = shutil.which('tmux')
_SESSION = 'monitor_cc_probe'

# ORCHESTRATOR


def main():
    workdir = Path(tempfile.mkdtemp(prefix='mcfix_tmux_'))
    _install_shim(workdir)
    os.environ['MONITOR_CC_ROOT'] = str(workdir)
    os.environ.pop('TMUX', None)
    tmux_launcher = importlib.import_module('src.tmux_launcher')
    janitor = importlib.import_module('src.monitor_janitor')
    results = []
    try:
        _kill_server()
        results += _checks_without_server(tmux_launcher, janitor, workdir)
        _new_session(_SESSION)
        results += _checks_with_session(tmux_launcher, janitor, workdir)
    finally:
        _kill_server()
        shutil.rmtree(workdir, ignore_errors=True)
    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(('PASS: ' if ok else 'FAIL: ') + name)
    print(f'{len(results) - len(failed)}/{len(results)} passed')
    sys.exit(1 if failed else 0)


# FUNCTIONS


def _install_shim(workdir: Path) -> None:
    shim = workdir / 'tmux'
    shim.write_text(f'#!/bin/sh\nexec {_REAL_TMUX} -L {_SOCKET} "$@"\n')
    shim.chmod(0o755)
    os.environ['PATH'] = f'{workdir}:{os.environ["PATH"]}'


def _kill_server() -> None:
    subprocess.run([_REAL_TMUX, '-L', _SOCKET, 'kill-server'], capture_output=True)


def _new_session(name: str) -> None:
    subprocess.run([_REAL_TMUX, '-L', _SOCKET, 'new-session', '-d', '-s', name, 'sleep 300'], check=True)


def _raises(exc_type, fn, *args) -> bool:
    try:
        fn(*args)
    except exc_type:
        return True
    return False


def _sweep_log(workdir: Path) -> str:
    path = workdir / 'src' / 'logs' / 'monitor_sweep.log'
    return path.read_text() if path.exists() else ''


def _checks_without_server(tl, janitor, workdir: Path) -> list:
    err = io.StringIO()
    with redirect_stderr(err):
        limit = tl.get_global_history_limit()
    janitor.list_monitor_sessions()
    entry = janitor.sweep_one_session('monitor_cc_ghost', 0, 100000.0, 10)
    log = _sweep_log(workdir)
    return [
        ('history limit without server returns None', limit is None),
        ('history limit without server names the skip on stderr', 'restore skipped' in err.getvalue()),
        ('kill_session on a missing session returns False', tl.kill_session('monitor_cc_ghost') is False),
        ('restart_panes on an unknown session raises', _raises(subprocess.CalledProcessError, tl.restart_panes, 'nosuch', None, 'workflow.py')),
        ('list_monitor_sessions logs NOSESSIONS rc=1', 'NOSESSIONS rc=1' in log),
        ('failed kill is logged KILL_FAILED', 'monitor_cc_ghost age=' in log and 'KILL_FAILED' in log),
        ('failed kill reports killed False', entry['killed'] is False),
    ]


def _checks_with_session(tl, janitor, workdir: Path) -> list:
    limit = tl.get_global_history_limit()
    cmds = {'a': 'sleep 30', 'b': 'sleep 30'}
    unresolved_parent = _raises(RuntimeError, tl._create_missing_window, _SESSION, 9, 'x',
                                [('a', None, None), ('b', 'zzz', '50%')], cmds)
    fill_unplaceable = _raises(RuntimeError, tl.restart_panes, _SESSION, None, 'workflow.py')
    entry = janitor.sweep_one_session(_SESSION, 0, 100000.0, 10)
    return [
        ('history limit with a server is the numeric string', limit is not None and limit.isdigit()),
        ('_create_missing_window raises on an unresolved parent pane', unresolved_parent),
        ('restart_panes raises when window 0 lacks its pane mode', fill_unplaceable),
        ('expired real session is killed and reported', entry['killed'] is True),
        ('KILLED line written for the real session', f'{_SESSION} age=' in _sweep_log(workdir) and 'KILLED' in _sweep_log(workdir)),
    ]


if __name__ == '__main__':
    main()
