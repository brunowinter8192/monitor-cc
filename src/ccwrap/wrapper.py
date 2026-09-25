# INFRASTRUCTURE

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import tty
from datetime import datetime
from pathlib import Path

from src.ccwrap import ansi_log as _alog

_DEFAULT_PROJECT = '/Users/brunowinter2000/Documents/ai/monitor-cc'
_SCRIPT_REL = 'src/claude_proxy_start.sh'
_LOG_DIR = Path(__file__).parent.parent / 'logs' / 'ccwrap'

# ORCHESTRATOR

def run(cmd: list, log_dir: Path) -> int:
    _prepare_log_dir(log_dir)
    ts = _timestamp()
    child_pid, master_fd = _spawn_child(cmd)
    _apply_winsize(master_fd)
    bin_fh, ansi_fh = _alog.open_log_pair(log_dir, ts, child_pid)
    _install_sigwinch(master_fd)
    stdin_fd = sys.stdin.fileno()
    old_attrs = _enter_raw_mode(stdin_fd)
    return _relay_session(master_fd, stdin_fd, bin_fh, ansi_fh, child_pid, old_attrs)

# FUNCTIONS

def _prepare_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    _alog.rotate_logs(log_dir)

def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')

def _spawn_child(cmd: list) -> tuple:
    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        os.execvp(cmd[0], cmd)
        os._exit(1)
    return child_pid, master_fd

def _apply_winsize(master_fd: int) -> None:
    rows, cols = _get_winsize()
    _set_winsize(master_fd, rows, cols)

def _get_winsize():
    buf = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
    return struct.unpack('HHHH', buf)[:2]

def _set_winsize(master_fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

def _install_sigwinch(master_fd: int) -> None:
    def _handler(signum, frame):
        r, c = _get_winsize()
        _set_winsize(master_fd, r, c)
    signal.signal(signal.SIGWINCH, _handler)

def _enter_raw_mode(stdin_fd: int):
    old_attrs = None
    if os.isatty(stdin_fd):
        old_attrs = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
    return old_attrs

def _relay_session(master_fd: int, stdin_fd: int, bin_fh, ansi_fh, child_pid: int, old_attrs) -> int:
    exit_code = 1
    try:
        _io_loop(master_fd, stdin_fd, bin_fh, ansi_fh)
        exit_code = _wait_child(child_pid)
    finally:
        _restore_session(master_fd, stdin_fd, bin_fh, ansi_fh, old_attrs)
    return exit_code

def _io_loop(master_fd: int, stdin_fd: int, bin_fh, ansi_fh) -> None:
    buf = b''
    fds = [master_fd, stdin_fd] if os.isatty(stdin_fd) else [master_fd]

    while True:
        rlist, _, _ = select.select(fds, [], [], 0.05)

        if master_fd in rlist:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError as e:
                if e.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            os.write(sys.stdout.fileno(), chunk)
            bin_fh.write(chunk)
            bin_fh.flush()
            combined = buf + chunk
            seqs = _alog.parse_sequences(combined)
            _alog.write_sequences(ansi_fh, seqs)
            buf = _carry_tail(combined)

        if stdin_fd in rlist:
            data = os.read(stdin_fd, 256)
            if data:
                os.write(master_fd, data)
            else:
                fds = [master_fd]

def _carry_tail(data: bytes) -> bytes:
    if not data:
        return b''
    if data[-1:] == b'\x1b':
        return b'\x1b'
    if len(data) >= 2 and data[-2:-1] == b'\x1b' and data[-1:] in (b'[', b']'):
        return data[-2:]
    return b''

def _wait_child(child_pid: int) -> int:
    _, status = os.waitpid(child_pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1

def _restore_session(master_fd: int, stdin_fd: int, bin_fh, ansi_fh, old_attrs) -> None:
    signal.signal(signal.SIGWINCH, signal.SIG_DFL)
    if old_attrs is not None:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
    bin_fh.close()
    ansi_fh.close()
    os.close(master_fd)
