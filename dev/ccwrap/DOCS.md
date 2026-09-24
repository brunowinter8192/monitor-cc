# dev/ccwrap/

## Role
Single regression check for the argument handling of `src/ccwrap/__main__.py`.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/ccwrap/missing_project_value_check.py`.

## Flow
Runs `python -m src.ccwrap --project` as a subprocess and checks exit code and message; the run exits before any child is spawned.

## Modules

### missing_project_value_check.py (19 LOC)

**Purpose:** Proves `--project` without a value exits 2 with a message.
**Reads:** nothing.
**Writes:** stdout pass/fail line, exit 1 on failure.
**Called by:** none; run manually.
**Calls out:** `python -m src.ccwrap` as a subprocess.

---

## State
No persistent state.
