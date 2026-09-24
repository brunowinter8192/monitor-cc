# dev/setup_py2app/

## Role
Regression checks for `setup_py2app.py` exit codes. The build script itself must never run: importing it calls `setup()`.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python dev/setup_py2app/exit_on_failure_checks.py`.

## Flow
Parses `setup_py2app.py`, executes only its function definitions with fake `subprocess` and `Path.home`, and asserts the exit codes.

## Modules

### exit_on_failure_checks.py (119 LOC)

**Purpose:** Proves a missing bundle src lib, a failing codesign and a failing bootstrap exit 1, and a successful bootstrap retry does not.
**Reads:** `setup_py2app.py` source text.
**Writes:** temp dirs only; stdout PASS/FAIL lines, exit 1 on failure.
**Called by:** none — run manually.
**Calls out:** none (AST extraction, no import).

---

## State
No persistent state.
