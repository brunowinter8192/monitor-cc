# dev/setup_py2app/

## Role
Regression checks for the exit codes of `setup_py2app.py`. The build script itself must never run: importing it starts the build.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/setup_py2app/exit_on_failure_checks.py`.

## Flow
Parses the build script, executes only its function definitions with fake subprocess and home lookups, and asserts the exit codes.

## Modules

### exit_on_failure_checks.py (137 LOC)

**Purpose:** Proves a missing bundle lib, a failing codesign and a failing bootstrap exit 1, and a successful bootstrap retry does not.
**Reads:** the build script's source text.
**Writes:** temp dirs only; stdout pass/fail lines, exit 1 on failure.
**Called by:** none; run manually.
**Calls out:** none; AST extraction, no import.

---

## State
No persistent state.
