# src/ccwrap/

## Role

Standalone PTY wrapper for Claude Code diagnostic logging. Spawns `src/claude_proxy_start.sh` as a child process in a PTY, forwards I/O bidirectionally (transparent passthrough), and logs every byte the child emits to a `.bin` file plus a `.ansi.log` file with one named ANSI sequence per line.

Phase 1 tool only — no filtering, no byte rewriting. Exists to capture the exact ANSI sequence that triggers Ghostty's scroll-to-bottom behavior during CC tool_use rendering.

**Touch this package** to: add ANSI sequence filtering (Phase 2), change log format, or extend sequence coverage.
**Do NOT touch** to: change Monitor_CC's main TUI, proxy, or session discovery — this package is fully standalone.

## Public Interface

Entry point: `python3 -m src.ccwrap [--project <path>]`

```python
from src.ccwrap.wrapper import run
# run(cmd: list, log_dir: Path) -> int
# Wraps cmd in a PTY, logs ANSI sequences to log_dir, returns child exit code.
```

## Flow

1. `__main__.py` parses `--project`, builds `['bash', 'src/claude_proxy_start.sh', '--project', <path>]`, calls `wrapper.run()`.
2. `wrapper.run()` creates log dir, rotates old logs, calls `pty.fork()` → child execs the command; parent sets PTY window size + installs SIGWINCH forwarder + opens log pair.
3. `_io_loop()` multiplexes master_fd and stdin_fd via `select` in a tight loop, forwarding data in both directions, writing raw bytes to `.bin` and parsed sequence names to `.ansi.log`.
4. Loop exits on PTY EOF (`OSError(EIO)` on Linux or 0-byte read on macOS). Parent calls `_wait_child()` and exits with child's exit code.

## Modules

### __init__.py (1 LOC)

**Purpose:** Package marker.
**Reads:** nothing. **Writes:** nothing.
**Called by:** Python import system.
**Calls out:** nothing.

---

### __main__.py (31 LOC)

**Purpose:** CLI entry point — parses `--project <path>` from argv, passes remaining args as passthrough to `claude_proxy_start.sh`, invokes `wrapper.run()`.
**Reads:** `sys.argv`.
**Writes:** `sys.exit(exit_code)`.
**Called by:** `python3 -m src.ccwrap`.
**Calls out:** `wrapper` (`.run`, `._DEFAULT_PROJECT`, `._SCRIPT_REL`, `._LOG_DIR`).

---

### wrapper.py (145 LOC)

**Purpose:** PTY lifecycle manager. `run()` forks a child into a PTY, manages bidirectional I/O via `select`, forwards SIGWINCH resizes, waits for child exit, and propagates exit code. Owns stdin raw-mode management (set/restore via `termios`).
**Reads:** `sys.stdin` (raw keystrokes in interactive mode); child PTY output via master_fd.
**Writes:** `sys.stdout` (raw bytes forwarded from child); `.bin` and `.ansi.log` via handles from `ansi_log.open_log_pair()`; SIGWINCH forwarded to child PTY via `TIOCSWINSZ`.
**Called by:** `__main__.py` (`run`).
**Calls out:** `ansi_log` (`.rotate_logs`, `.open_log_pair`, `.parse_sequences`, `.write_sequences`); stdlib `pty`, `select`, `termios`, `tty`, `fcntl`, `signal`.

---

### ansi_log.py (77 LOC)

**Purpose:** ANSI byte-stream parser and log-file manager. `parse_sequences()` extracts named ANSI tokens (CSI, OSC, ESC+char, C0) from a byte chunk using a compiled regex. `rotate_logs()` deletes oldest `.bin`/`.ansi.log` pairs beyond the keep-count. `open_log_pair()` opens a `.bin` + `.ansi.log` file pair. `write_sequences()` appends `<unix_ts>\t<name>\t<hex>` lines to the ansi.log.
**Reads:** nothing from disk at runtime (rotation reads dir listings via `glob`).
**Writes:** `.bin` and `.ansi.log` files under `src/logs/ccwrap/` (handles returned to caller).
**Called by:** `wrapper.py` (all four public functions).
**Calls out:** stdlib `re`, `time`, `pathlib`.

---

## State

No module-level mutable state. All state is local to `run()` call.

## Gotchas

- **macOS PTY EOF semantics differ from Linux.** On Linux, reading from master_fd after the child exits raises `OSError(errno.EIO)`. On macOS, `os.read(master_fd, N)` returns `b''` (0 bytes). `_io_loop` handles both: catch `EIO` for Linux, break on empty read for macOS.
- **`_wait_child` called BEFORE `os.close(master_fd)` in the finally block.** If master_fd is closed before `waitpid`, the child receives SIGHUP (PTY disconnect → session-leader exit → SIGHUP to process group), which masks the real exit code (returns 128+1=129). Closing master_fd happens in `finally` AFTER `_wait_child` returns.
- **stdin raw mode is skipped when stdin is not a TTY.** The wrapper checks `os.isatty(stdin_fd)` before calling `tty.setraw()` and before adding `stdin_fd` to the select watch list. When run inside a task runner (non-tty stdin), stdin is simply not forwarded — the child gets an empty stdin from its slave PTY.
- **SIGWINCH handler deregistered before master_fd closes.** The `finally` block sets `signal.SIGWINCH = SIG_DFL` as its first step to prevent the handler from calling `TIOCSWINSZ` on a closed fd if a resize signal races with cleanup.
- **Log rotation is mtime-based** — newest mtime = most recently written. Pairs are matched by stem: `<stem>.bin` + `<stem>.ansi.log`. If only one half of a pair exists (e.g., crash mid-write), the orphan `.ansi.log` is NOT cleaned up by `rotate_logs` (it only iterates `.bin` files). Tolerable for Phase 1.
- **Partial ESC sequence carry buffer** (`_carry_tail`) handles chunks that split an escape sequence across two reads. Only the last 1–2 bytes are carried (ESC alone, or ESC+`[`/`]`). Longer partial sequences (e.g., mid-CSI parameter bytes) are not carried — would only matter for very unlucky 4096-byte boundaries and the sequence would just log as two fragments.

## Usage

```bash
# Wrap real CC session (default project = Monitor_CC):
python3 -m src.ccwrap

# With explicit project:
python3 -m src.ccwrap --project /path/to/my/project

# Smoke test (quick-exit command, write logs to src/logs/ccwrap/):
python3 -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from src.ccwrap.wrapper import run
run(['bash', '-c', r'echo hi; printf \"\033[2J\033[H\"; echo done'], Path('src/logs/ccwrap'))
"
```

Logs land in `src/logs/ccwrap/` (gitignored via `src/logs/` in `.gitignore`).
