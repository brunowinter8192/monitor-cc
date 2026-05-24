# ccwrap Phase 1 — PTY Wrapper with Diagnostic ANSI Logging

## Context

Follow-up to `initial.md` (Hypothesis 3 open: CC TUI emits ANSI cursor/scroll directives
that bypass Ghostty's `scroll-to-bottom` config). Phase 1 builds the diagnostic tooling
to identify the exact sequence. Phase 2 (filter/suppress the trigger) is not built here.

---

## What was built

`src/ccwrap/` — standalone Python package, 254 LOC across 4 files:

| File | LOC | Role |
|---|---|---|
| `__init__.py` | 1 | package marker |
| `__main__.py` | 31 | CLI: parse `--project`, build cmd, call `wrapper.run()` |
| `wrapper.py` | 145 | PTY fork, select loop, SIGWINCH, stdin raw mode, exit propagation |
| `ansi_log.py` | 77 | ANSI regex parser, log file open/rotate/write |

Entry point: `python3 -m src.ccwrap [--project <path>]`

Logs written to `src/logs/ccwrap/` (gitignored):
- `<YYYYMMDD-HHMMSS>-<pid>.bin` — raw byte stream, unmodified
- `<YYYYMMDD-HHMMSS>-<pid>.ansi.log` — one named sequence per line: `<unix_ts_ms>\t<name>\t<hex>`

Log rotation: at startup, keep newest 10 `.bin`/`.ansi.log` pairs, delete older.

---

## Why this layout

**`pty.fork()` over `pty.spawn()` or raw `os.openpty()`:** `pty.spawn()` runs its own internal loop with no hook for mid-stream processing. `os.openpty() + os.fork()` is equivalent to `pty.fork()` but requires manual `os.setsid()` + `TIOCSCTTY` in the child — `pty.fork()` handles this automatically.

**`ansi_log.py` split from `wrapper.py`:** ANSI parsing has no PTY state and is independently testable. The split proved useful — the parser was unit-tested standalone before the PTY loop was debugged.

**`__main__.py` separate from `wrapper.py`:** `wrapper.run()` can be imported and called with an arbitrary `cmd` list (used in smoke tests), without going through the CLI arg parser that always invokes `claude_proxy_start.sh`.

---

## Edge cases handled

| Edge case | Resolution |
|---|---|
| macOS PTY EOF differs from Linux | Linux raises `OSError(EIO)` on master_fd read after child exits; macOS returns `b''` (0 bytes). Both handled: `if not chunk: break` after the `except OSError as e: if e.errno == errno.EIO: break`. |
| `_wait_child` must run before `os.close(master_fd)` | Closing master_fd first sends SIGHUP to the child (PTY disconnect → session-leader exit → SIGHUP to process group). The `run()` try block calls `_wait_child()` BEFORE the `finally` clause that closes master_fd. |
| SIGWINCH handler + closed master_fd race | `finally` block sets `signal.SIGWINCH = SIG_DFL` as its FIRST step before closing master_fd. Prevents the handler from calling `TIOCSWINSZ` on a closed fd. |
| stdin not a TTY (task runner, pipe) | `os.isatty(stdin_fd)` checked before raw-mode and before adding stdin to select watchlist. Non-tty stdin = not forwarded; child gets empty slave PTY stdin. |
| stdin EOF (Ctrl-D in interactive mode) | `os.read(stdin_fd)` returning `b''` removes stdin_fd from the watchlist rather than breaking the loop — keeps reading child output until the child itself exits. |
| Partial ESC sequences at 4096-byte boundaries | `_carry_tail()` retains the last 1–2 bytes if they form an incomplete ESC start (`\x1b` alone or `\x1b[`/`\x1b]`). Longer mid-sequence splits (rare at PTY read boundaries) log as fragments — acceptable for Phase 1 diagnostics. |
| stdin raw mode not restored on crash | `try/finally` in `wrapper.run()` restores `old_attrs` via `termios.tcsetattr(TCSADRAIN)` regardless of exit path. |

---

## Smoke test result

Command: `bash -c 'echo hello; printf "\033[2J\033[H"; echo world'`

stdout (21 bytes): `hello\r\n\033[2J\033[Hworld\r\n`

`.ansi.log`:
```
1779639315.942	CR	0d
1779639315.942	CSI 2J	1b5b324a
1779639315.942	CSI H	1b5b48
1779639315.942	CR	0d
```

`CSI 2J` (erase display) and `CSI H` (cursor home) correctly identified. Exit code 0.

---

## What is known NOT to work yet

- **No CC session capture tested.** `claude_proxy_start.sh` requires `mitmdump` + `~/.local/bin/claude-114` and a real user session. Running from inside a worker tmux pane cannot provide an interactive PTY for CC's full TUI (the worker's stdin is a task-runner pipe, not a terminal with Ghostty on the other end). This is a structural limitation of the test environment, not the wrapper code.
- **Phase 1 is passthrough only.** No filtering, no suppression of any sequence. The diagnostic value is in reading the `.ansi.log` after a real CC session and identifying which CSI/OSC sequence correlates with the Ghostty viewport jump at tool_use render time.
- **OSC body parsing is minimal.** OSC sequences are logged as `OSC <num>` (the numeric prefix before `;`). The payload body is not preserved in the `.ansi.log`. If the trigger turns out to be an OSC payload value (not just the sequence type), the `.bin` file must be consulted for full bytes.
- **Partial-sequence carry covers only the last 1–2 bytes.** A very long OSC sequence split exactly at a 4096-byte read boundary would be logged as two fragments. Hasn't been observed in practice.

---

## What Phase 2 needs

1. Read a `.ansi.log` from a real CC session containing tool_use rendering events.
2. Identify the sequence name that correlates with Ghostty viewport jumps (Hypothesis 3 candidate: `CSI 2J`, `CSI H`, `CSI r` scroll-region, or a private mode toggle like `CSI ?47h`/`CSI ?1049h`).
3. Add a byte-rewriting filter in `wrapper.py` or a new `filter.py`: intercept the identified sequence on the master_fd → stdout path, either suppress it or replace it with a no-op.
4. Test with `python3 -m src.ccwrap --project /path/to/project` in a real Ghostty window and verify the viewport no longer jumps.
