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

from . import ansi_log as _alog

_DEFAULT_PROJECT = '/Users/brunowinter2000/Documents/ai/monitor-cc'
_SCRIPT_REL = 'src/claude_proxy_start.sh'
_LOG_DIR = Path(__file__).parent.parent / 'logs' / 'ccwrap'

# ORCHESTRATOR


# Wrap cmd in a PTY, forward I/O bidirectionally, log ANSI sequences to log_dir
def run(cmd: list, log_dir: Path) -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    _alog.rotate_logs(log_dir)

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    child_pid, master_fd = pty.fork()

    if child_pid == 0:
        # Child: exec the target command (PTY slave is already the controlling terminal)
        os.execvp(cmd[0], cmd)
        os._exit(1)

    # Parent: set initial PTY window size to match our terminal
    rows, cols = _get_winsize()
    _set_winsize(master_fd, rows, cols)

    bin_fh, ansi_fh = _alog.open_log_pair(log_dir, ts, child_pid)
    _install_sigwinch(master_fd)

    old_attrs = None
    stdin_fd = sys.stdin.fileno()
    if os.isatty(stdin_fd):
        old_attrs = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)

    exit_code = 1
    try:
        _io_loop(master_fd, stdin_fd, bin_fh, ansi_fh)
        # Wait for child before closing master_fd — closing it first sends SIGHUP to child
        exit_code = _wait_child(child_pid)
    finally:
        # Deregister SIGWINCH before closing master_fd to avoid handler racing on closed fd
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        if old_attrs is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
        bin_fh.close()
        ansi_fh.close()
        os.close(master_fd)

    return exit_code

# FUNCTIONS


# Return (rows, cols) of the current terminal; fall back to 24x80 if not a tty
def _get_winsize():
    try:
        buf = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
        return struct.unpack('HHHH', buf)[:2]
    except OSError:
        return (24, 80)


# Set the window size on a PTY master fd
def _set_winsize(master_fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))


# Install a SIGWINCH handler that forwards terminal resize to the PTY
def _install_sigwinch(master_fd: int) -> None:
    def _handler(signum, frame):
        r, c = _get_winsize()
        _set_winsize(master_fd, r, c)
    signal.signal(signal.SIGWINCH, _handler)


# Bidirectional I/O loop: forward stdin→PTY and PTY→stdout+logs until child exits (EIO)
def _io_loop(master_fd: int, stdin_fd: int, bin_fh, ansi_fh) -> None:
    buf = b''  # partial-sequence carry buffer for ANSI parser
    # Only watch stdin when it is a real terminal; pipes/heredocs would EOF immediately
    fds = [master_fd, stdin_fd] if os.isatty(stdin_fd) else [master_fd]

    while True:
        rlist, _, _ = select.select(fds, [], [], 0.05)

        if master_fd in rlist:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError as e:
                if e.errno == errno.EIO:
                    break   # Linux: EIO when child exits and slave is closed
                raise
            if not chunk:
                break       # macOS: 0-byte read signals PTY EOF
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
                # stdin EOF: stop forwarding input but keep loop alive for remaining child output
                fds = [master_fd]


# Return the last partial ESC sequence if data ends mid-sequence, else b''
def _carry_tail(data: bytes) -> bytes:
    if not data:
        return b''
    if data[-1:] == b'\x1b':
        return b'\x1b'
    if len(data) >= 2 and data[-2:-1] == b'\x1b' and data[-1:] in (b'[', b']'):
        return data[-2:]
    return b''


# Wait for child_pid and return its exit code
def _wait_child(child_pid: int) -> int:
    _, status = os.waitpid(child_pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1
