# dev/constants/

## Role
Byte-identity regression harness for `src/constants.py` and the modules it was split by constant cluster into (`src/colors.py`, `src/core/modes.py`, `src/pane_error_log.py`). Add a script here (or extend this one) when a future split of any of these modules needs a before/after correctness proof.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/constants/split_byte_identity.py`.

## Flow
Resolves a fixed list of 44 top-level `UPPER_CASE` names through a `_NEW_LOCATIONS` map to their current module, reads each value via `getattr`, hashes `{name: repr(value)}`, and prints one `HASH:` line to stdout.

## Modules

### split_byte_identity.py (68 LOC)

**Purpose:** Byte-identity harness for `src/constants.py`'s constant clusters — resolves 44 fixed names to their current module and hashes `{name: repr(value)}`.
**Reads:** nothing external.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Kind:** verification aid, not a test: it prints a hash and asserts nothing, a human compares two runs taken before and after a change. Input is the imported constants themselves, so two runs on the same tree give the same hash.
**Called by:** none — run manually; re-run after any further `src/constants.py` split.
**Calls out:** `src.constants`, `src.colors`, `src.core.modes`, `src.pane_error_log` — all imported via a dedicated function (`_resolve`, through `importlib`), not a module-level `from src.` line, per `block_dev_imports_src`.

---

## State
No module-level shared state beyond the two frozen name lists (`_NAMES`, `_NEW_LOCATIONS`) and their derived cluster lists, all module constants read only, never mutated after import.
