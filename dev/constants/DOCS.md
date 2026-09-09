# dev/constants/

## Role

Byte-identity regression harness for `src/constants.py` splits by constant cluster. Add a script
here when a future `constants.py` (or its successor modules') split needs a before/after
correctness proof.

## Modules

### split_byte_identity.py (104 LOC, new 2026-09, constants-split milestone)

**Purpose:** Byte-identity harness for `src/constants.py`'s split into `src/colors.py` (ANSI
colors + backgrounds, `PASTEL_*` cluster), `src/core/modes.py` (`MODE_*` cluster),
`src/pane_error_log.py` (`PANE_ERROR_LOG_*` cluster, absorbed into the module that already owns
that concern), and the residual `src/constants.py` (timing/size limits, `TOOL_BLOCKLIST`, and the
`HOOK_*` cluster — left in place per Main's direction: it has zero importers anywhere in
`src/`/`dev/`, so a dedicated module would be dead code on arrival, and it's the only cluster left
in `constants.py` once the other three leave, which satisfies the split rule on its own). Hardcodes
the exact 70 top-level UPPER_CASE names that existed in `constants.py` at the moment this harness
was built (frozen as a literal list — dynamic discovery via `vars()` would only find the 35 or so
still there post-split), resolves each through a `_NEW_LOCATIONS` map (defaults to `src.constants`;
updated in the same commit as the split for every name that actually moved), and hashes
`{name: repr(value)}`.
**Reads:** nothing external.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Run:** `./venv/bin/python dev/constants/split_byte_identity.py`
**Calls out:** `src.constants`, `src.colors`, `src.core.modes`, `src.pane_error_log` — all
imported via a dedicated function (`_resolve`, called per-name through `importlib`), not a
module-level `from src.` line, per `block_dev_imports_src`.

**`repr(frozenset(...))` non-determinism gotcha:** `TOOL_BLOCKLIST` is a `frozenset` of strings;
Python's per-process string-hash randomization (`PYTHONHASHSEED`) makes `repr(frozenset(...))`'s
element order vary between separate process runs — confirmed empirically: 3 runs of a naive
version of this harness produced 3 different hashes with ZERO code changes in between. `_dump_values`
sorts `(frozen)set` values before `repr()`-ing them to neutralize this; verified stable across 3
runs before trusting the baseline. Any future addition of a `set`/`frozenset`-valued constant to
this harness's name list must go through the same `_stable_repr` path, not a bare `repr()`.

Status: hash `fa6f42c25ef89eb9d6d5bd9e90ad66697c29e6d1d950bd670e0eda8d7fd60bc3` — identical before
and after the constants-split milestone.
