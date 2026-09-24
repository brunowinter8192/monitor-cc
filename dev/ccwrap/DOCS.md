# dev/ccwrap/

## Role
Single regression check for `src/ccwrap/__main__.py` argument handling.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python dev/ccwrap/missing_project_value_check.py`.

## Flow
Runs `python -m src.ccwrap --project` as a subprocess and checks exit code and message; the run exits before any child is spawned.

## Modules

### missing_project_value_check.py (19 LOC)

**Purpose:** Proves `--project` without a value exits 2 with a message.
**Reads:** nothing.
**Writes:** stdout PASS/FAIL line, exit 1 on failure.
**Called by:** none — run manually.
**Calls out:** `python -m src.ccwrap` (subprocess).

---

## State
No persistent state.
