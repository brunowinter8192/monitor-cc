# dev/constants/

## Role
Byte-identity regression harness for `src/constants.py` and the modules its constant clusters were split into (`src/colors.py`, `src/core/modes.py`, `src/pane_error_log.py`). Add or extend a script when a further split needs a before/after correctness proof.

## Public Interface
No `__init__.py`. Entry point: `./venv/bin/python dev/constants/split_byte_identity.py`.

## Flow
Resolves a fixed list of top-level constant names to their current module, reads each value, hashes the name-to-value mapping and prints one hash line.

## Modules

### split_byte_identity.py (68 LOC)

**Purpose:** Verification aid, not a test: hashes the values of a fixed constant list across the split modules for before/after comparison.
**Reads:** nothing external; the imported constants themselves.
**Writes:** stdout only (one hash line).
**Called by:** none; re-run after any further constants split.
**Calls out:** `src.constants`, `src.colors`, `src.core.modes`, `src.pane_error_log`, imported lazily to satisfy the dev-imports-src hook.

---

## State
No shared state beyond frozen name lists held as module constants.
