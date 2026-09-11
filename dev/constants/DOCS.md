# dev/constants/

## Role

Byte-identity regression harness for `src/constants.py` and the modules it was split by constant
cluster into (`src/colors.py`, `src/core/modes.py`, `src/pane_error_log.py`). Add a script here
(or extend this one) when a future split of any of these modules needs a before/after correctness
proof.

## Modules

### split_byte_identity.py (104 LOC)

**Purpose:** Byte-identity harness for `src/constants.py`'s constant clusters — resolves a fixed
list of top-level `UPPER_CASE` names through a `_NEW_LOCATIONS` map to their current module
(`src.constants` by default, `src.colors`/`src.core.modes`/`src.pane_error_log` for moved
clusters) and hashes `{name: repr(value)}`.
**Reads:** nothing external.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Called by:** none — run manually; re-run after any further `src/constants.py` split.
**Calls out:** `src.constants`, `src.colors`, `src.core.modes`, `src.pane_error_log` — all
imported via a dedicated function (`_resolve`, through `importlib`), not a module-level `from
src.` line, per `block_dev_imports_src`.

---

## Gotchas

**`repr(frozenset(...))` is non-deterministic across process runs.** `TOOL_BLOCKLIST` is a
`frozenset` of strings; Python's per-process string-hash randomization
(`PYTHONHASHSEED`) makes `repr(frozenset(...))`'s element order vary run to run — confirmed
empirically (3 runs of a naive harness produced 3 different hashes with zero code changes).
`_dump_values` sorts `(frozen)set` values before `repr()`-ing them to neutralize this. Any future
addition of a `set`/`frozenset`-valued constant to the name list must go through the same
`_stable_repr` path, not a bare `repr()`.
