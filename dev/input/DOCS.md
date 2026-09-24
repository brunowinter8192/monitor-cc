# dev/input/

## Role
Regression checks for `src/input/click_handler.py` failure paths. Touch when changing raw stdin, mouse parsing or clipboard handling.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python dev/input/tripwire_checks.py`.

## Flow
Child processes with a null or pty stdin, a pipe as fake stdin fd, and a fake `pbcopy` on PATH drive `set_raw_stdin`, `read_mouse_event`, `copy_to_clipboard` and `restore_terminal`.

## Modules

### tripwire_checks.py (123 LOC)

**Purpose:** Proves a non-tty stdin, a malformed SGR field and a failing `pbcopy` raise, valid sequences still parse, and a failing terminal restore is logged.
**Reads:** nothing external; fake `pbcopy` and log in a temp dir.
**Writes:** temp dir only; stdout PASS/FAIL lines, exit 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.input.click_handler`, `src.pane_error_log` (via `importlib`).

---

## State
No persistent state.
