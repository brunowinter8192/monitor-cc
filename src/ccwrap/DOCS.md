# src/ccwrap/

## Role

Standalone PTY wrapper for Claude Code diagnostic logging: runs `claude_proxy_start.sh` in a PTY, passes I/O through unchanged and logs every child byte plus named ANSI sequences. Touch to extend sequence coverage or the log format; not for the main TUI, proxy or session discovery.

## Public Interface

Entry point: `python3 -m src.ccwrap [--project <path>]`. `__init__.py` is empty; `wrapper.py` exposes the PTY runner used by `__main__.py`.

## Flow

1. `__main__.py` parses `--project`, builds the `claude_proxy_start.sh` command and hands it to `wrapper.py`.
2. `wrapper.py` rotates old logs, forks the command into a PTY, forwards window resizes and opens the log pair.
3. Its I/O loop multiplexes PTY and stdin, writing raw bytes to `.bin` and parsed sequence names to `.ansi.log`.
4. The loop ends on PTY EOF; the parent waits for the child and exits with its exit code.

## Modules

### __main__.py (38 LOC)

**Purpose:** CLI entry point; parses the project argument, passes remaining args to the start script and invokes the wrapper.
**Reads:** `sys.argv`.
**Writes:** the process exit code.
**Called by:** `python3 -m src.ccwrap`.
**Calls out:** none.

---

### wrapper.py (143 LOC)

**Purpose:** PTY lifecycle manager: fork, bidirectional I/O, window-resize forwarding, stdin raw-mode handling, exit-code propagation.
**Reads:** stdin keystrokes (when a tty) and child PTY output.
**Writes:** stdout (forwarded child bytes); the `.bin` and `.ansi.log` pair; window size to the child PTY.
**Called by:** `__main__.py`.
**Calls out:** none.

---

### ansi_log.py (69 LOC)

**Purpose:** ANSI byte-stream parser and log-file manager (parsing, rotation, opening the log pair, writing sequence lines).
**Reads:** directory listings for rotation.
**Writes:** `.bin` and `.ansi.log` pairs under the caller-supplied log directory (default: ccwrap folder under the gitignored src logs).
**Called by:** `wrapper.py`.
**Calls out:** none.

---
