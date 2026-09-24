# INFRASTRUCTURE
import importlib
import os
import pty
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.refactoring.check_group import assert_checks
from dev.refactoring.strand_runner import strand_workflow

_RAISE_CODE = "import src.input.click_handler as c; c.set_raw_stdin()"
_OK_CODE = "import src.input.click_handler as c; print(c.set_raw_stdin())"
_STRAND_NAMES = ['strand_stdin', 'strand_mouse', 'strand_clipboard', 'strand_restore']

# ORCHESTRATOR


def main():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, title='input tripwire checks'))


# FUNCTIONS


def strand_stdin() -> None:
    assert_checks(_stdin_checks())


def strand_mouse() -> None:
    _workdir, click, _pane_log = _setup()
    assert_checks(_mouse_checks(click))


def strand_clipboard() -> None:
    workdir, click, _pane_log = _setup()
    assert_checks(_clipboard_checks(click, workdir))


def strand_restore() -> None:
    _workdir, click, pane_log = _setup()
    assert_checks(_restore_checks(click, pane_log))


def _setup() -> tuple:
    workdir = Path(tempfile.mkdtemp(prefix='mcfix_input_'))
    click = importlib.import_module('src.input.click_handler')
    pane_log = importlib.import_module('src.pane_error_log')
    pane_log.PANE_ERROR_LOG_PATH = str(workdir / 'pane_error.log')
    return workdir, click, pane_log


def _child(code: str, stdin) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-c', code], stdin=stdin, cwd=_ROOT, capture_output=True, text=True)


def _stdin_checks() -> list:
    no_tty = _child(_RAISE_CODE, subprocess.DEVNULL)
    master, slave = pty.openpty()
    try:
        with_tty = _child(_OK_CODE, slave)
    finally:
        os.close(master)
        os.close(slave)
    return [
        ('set_raw_stdin on a non-tty stdin raises', no_tty.returncode != 0 and 'termios.error' in no_tty.stderr),
        ('set_raw_stdin on a pty returns True', with_tty.returncode == 0 and with_tty.stdout.strip() == 'True'),
    ]


def _mouse_event(click, payload: bytes):
    read_fd, write_fd = os.pipe()
    click._stdin_fd = read_fd
    os.write(write_fd, payload)
    try:
        return click.read_mouse_event('\033')
    except ValueError:
        return 'ValueError'
    finally:
        os.close(read_fd)
        os.close(write_fd)


def _mouse_checks(click) -> list:
    return [
        ('press sequence parses', _mouse_event(click, b'[<0;10;5M') == (0, 10, 5)),
        ('release sequence is (-1,-1,-1)', _mouse_event(click, b'[<0;10;5m') == (-1, -1, -1)),
        ('non-mouse terminator returns None', _mouse_event(click, b'xM') is None),
        ('sequence never terminated returns None', _mouse_event(click, b'[A') is None),
        ('non-numeric SGR field raises', _mouse_event(click, b'[<a;1;2M') == 'ValueError'),
        ('SGR with two fields raises', _mouse_event(click, b'[<1;2M') == 'ValueError'),
    ]


def _fake_pbcopy(workdir: Path, rc: int) -> None:
    shim = workdir / 'pbcopy'
    shim.write_text(f'#!/bin/sh\ncat >/dev/null\nexit {rc}\n')
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)


def _clipboard_result(click, workdir: Path, rc: int) -> str:
    _fake_pbcopy(workdir, rc)
    old_path = os.environ['PATH']
    os.environ['PATH'] = f'{workdir}:{old_path}'
    try:
        click.copy_to_clipboard('x')
        return 'ok'
    except subprocess.CalledProcessError:
        return 'CalledProcessError'
    finally:
        os.environ['PATH'] = old_path


def _clipboard_checks(click, workdir: Path) -> list:
    return [
        ('pbcopy rc 0 passes', _clipboard_result(click, workdir, 0) == 'ok'),
        ('pbcopy rc 1 raises', _clipboard_result(click, workdir, 1) == 'CalledProcessError'),
    ]


class _BrokenStdin:
    def fileno(self):
        raise ValueError('closed')


def _restore_checks(click, pane_log) -> list:
    old_stdin = sys.stdin
    click._original_terminal_settings = [0]
    sys.stdin = _BrokenStdin()
    try:
        click.restore_terminal()
    finally:
        sys.stdin = old_stdin
        click._original_terminal_settings = None
    text = Path(pane_log.PANE_ERROR_LOG_PATH).read_text() if Path(pane_log.PANE_ERROR_LOG_PATH).exists() else ''
    return [('restore_terminal failure is logged via log_pane_error', '[input] error' in text)]


if __name__ == '__main__':
    main()
