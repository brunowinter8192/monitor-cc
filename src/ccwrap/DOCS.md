# src/ccwrap/

## Role

Standalone PTY wrapper for Claude Code diagnostic logging. Spawns `src/claude_proxy_start.sh` as a
child process in a PTY, forwards I/O bidirectionally (transparent passthrough), and logs every
byte the child emits to a `.bin` file plus a `.ansi.log` file with one named ANSI sequence per
line. Phase 1 tool only — no filtering, no byte rewriting; exists to capture the exact ANSI
sequence that triggers a terminal's scroll-to-bottom behavior during CC tool_use rendering. Touch
this package to add ANSI sequence filtering, change the log format, or extend sequence coverage.
Do NOT touch it to change Monitor_CC's main TUI, proxy, or session discovery — this package is
fully standalone.

## Public Interface

Entry point: `python3 -m src.ccwrap [--project <path>]`

```python
from src.ccwrap.wrapper import run
# run(cmd: list, log_dir: Path) -> int
```

## Flow

1. `__main__.py` parses `--project`, builds `['bash', 'src/claude_proxy_start.sh', '--project', <path>]`, calls `wrapper.run()`.
2. `wrapper.run()` creates the log dir, rotates old logs, calls `pty.fork()` — the child execs the command; the parent sets the PTY window size, installs a SIGWINCH forwarder, and opens the log pair.
3. `_io_loop()` multiplexes `master_fd` and `stdin_fd` via `select`, forwarding data both ways, writing raw bytes to `.bin` and parsed sequence names to `.ansi.log`.
4. Loop exits on PTY EOF (`OSError(EIO)` on Linux, 0-byte read on macOS). The parent waits for the child and exits with its exit code.

## Modules

### __main__.py (31 LOC)

**Purpose:** CLI entry point — parses `--project <path>` from argv, passes remaining args through to `claude_proxy_start.sh`, invokes `wrapper.run()`.
**Reads:** `sys.argv`.
**Writes:** `sys.exit(exit_code)`.
**Called by:** `python3 -m src.ccwrap`.
**Calls out:** none.

---

### wrapper.py (132 LOC)

**Purpose:** PTY lifecycle manager. `run()` forks a child into a PTY, manages bidirectional I/O via `select`, forwards SIGWINCH resizes, waits for child exit, and propagates the exit code. Owns stdin raw-mode management (set/restore via `termios`).
**Reads:** `sys.stdin` (raw keystrokes, when stdin is a tty); child PTY output via `master_fd`.
**Writes:** `sys.stdout` (raw bytes forwarded from child); `.bin` and `.ansi.log` via handles from `ansi_log.open_log_pair()`; forwards SIGWINCH to the child PTY via `TIOCSWINSZ`.
**Called by:** `__main__.py` (`run`).
**Calls out:** none.

---

### ansi_log.py (69 LOC)

**Purpose:** ANSI byte-stream parser and log-file manager. `parse_sequences()` extracts named ANSI tokens (CSI, OSC, ESC+char, C0) from a byte chunk via a compiled regex. `rotate_logs()` deletes the oldest `.bin`/`.ansi.log` pairs beyond the keep-count. `open_log_pair()` opens a `.bin` + `.ansi.log` file pair. `write_sequences()` appends `<unix_ts>\t<name>\t<hex>` lines to the ansi.log.
**Reads:** nothing at parse time; directory listings via `glob` for rotation.
**Writes:** `.bin` and `.ansi.log` pairs under the caller-supplied `log_dir` (default: the ccwrap folder under the gitignored src logs directory).
**Called by:** `wrapper.py` (all four public functions).
**Calls out:** none.

---

## Gotchas

- **macOS PTY EOF differs from Linux.** Reading from `master_fd` after the child exits raises `OSError(errno.EIO)` on Linux, but returns `b''` on macOS. `_io_loop` handles both explicitly.
- **`_wait_child` runs before `os.close(master_fd)`.** If `master_fd` closed first, the child receives SIGHUP (PTY disconnect → session-leader exit → SIGHUP to the process group), masking the real exit code with `128+1=129`. The `finally` block closes `master_fd` only after `_wait_child` has already returned.
- **stdin raw mode is skipped when stdin is not a tty** (`os.isatty(stdin_fd)` guards both `tty.setraw()` and adding `stdin_fd` to the select watch list) — under a non-tty runner, the child simply never receives stdin.
- **SIGWINCH handler is deregistered before `master_fd` closes** (`finally` sets it to `SIG_DFL` first) to prevent a racing resize signal from calling `TIOCSWINSZ` on an already-closed fd.
- **Log rotation is mtime-based** and matches pairs by stem (`<stem>.bin` + `<stem>.ansi.log`); `rotate_logs` only iterates `.bin` files, so an orphaned `.ansi.log` from a crash mid-write is never cleaned up.
- **`_carry_tail` only carries 1-2 bytes** of a split escape sequence across reads (ESC alone, or ESC+`[`/`]`) — a longer partial sequence split at a 4096-byte read boundary logs as two fragments instead of one.
