# dev/input/

## Role
Regression checks for the failure paths of `src/input/click_handler.py`. Touch when changing raw stdin, mouse parsing or clipboard handling.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/input/tripwire_checks.py`.

## Flow
Child processes with a null or pty stdin, a pipe as fake stdin and a fake `pbcopy` on PATH drive the raw-mode setup, mouse parsing, clipboard copy and terminal restore paths.

## Modules

### tripwire_checks.py (145 LOC)

**Purpose:** Proves a non-tty stdin, a malformed SGR field and a failing `pbcopy` raise, valid sequences still parse and a failing terminal restore is logged.
**Reads:** nothing external; fake `pbcopy` and log in a temp dir.
**Writes:** temp dir only; stdout pass/fail lines, exit 1 on failure.
**Called by:** none; run manually. The four check groups run as parallel strands.
**Calls out:** `src.input.click_handler`, `src.pane_error_log` via `importlib`; the strand runner and check helper in `dev/refactoring/`.

---

## State
No persistent state.
