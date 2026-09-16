## Salvage from dev/constants/split_byte_identity.py

```
"""
Byte-identity harness for src/constants.py's split by constant cluster into src/colors.py (ANSI
colors + backgrounds, PASTEL_* cluster), src/core/modes.py (MODE_* cluster), src/pane_error_log.py
(PANE_ERROR_LOG_* cluster absorbed into the module that already owns that concern), and the
residual src/constants.py (timing/size limits + TOOL_BLOCKLIST — zero clusters left). The HOOK_*
cluster + HOOK_EVENT_CATEGORIES (26 names) had zero importers anywhere in src/ or dev/ and were
deleted outright (control-flow integrity fixes, refactor phase 4) rather than migrated to a new
module — removed from _NAMES below, not tracked in _NEW_LOCATIONS.

BEFORE the split: every name below resolves through _NEW_LOCATIONS' default (src.constants,
where they all still live); dumps {name: repr(value)} and hashes it.
AFTER the split: _NEW_LOCATIONS is updated (same commit as the split) to point each moved name at
its new module; the same 44 names resolve from their new homes and hash identically.

Usage (from project root):
    ./venv/bin/python dev/constants/split_byte_identity.py

Prints one HASH line. Run before and after the split; the hash must match.
"""
```

```
# The 44 top-level UPPER_CASE names in src/constants.py that are still live post-HOOK_*-deletion —
# frozen here rather than discovered dynamically via vars(), since after the split most of them
# are no longer present in src.constants at all.
```

```
# Post-split home for every name that moves out of src/constants.py. A name absent here is
# assumed to still live in src.constants — true for the 9 residual timing/size-limit names and
# TOOL_BLOCKLIST.
```

```
# repr(frozenset(...)) / repr(set(...)) order depends on PYTHONHASHSEED's per-process string-hash
# randomization — TOOL_BLOCKLIST would otherwise make this harness's own hash non-reproducible
# across separate runs regardless of any src/constants.py change. Sort (frozen)sets before repr.
```

## Salvage from dev/constants/DOCS.md

Nothing cut — the pre-existing `## Role` and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section has no home in the new fixed format and moved here in full:

```
## Gotchas

**`repr(frozenset(...))` is non-deterministic across process runs.** `TOOL_BLOCKLIST` is a
`frozenset` of strings; Python's per-process string-hash randomization
(`PYTHONHASHSEED`) makes `repr(frozenset(...))`'s element order vary run to run — confirmed
empirically (3 runs of a naive harness produced 3 different hashes with zero code changes).
`_dump_values` sorts `(frozen)set` values before `repr()`-ing them to neutralize this. Any future
addition of a `set`/`frozenset`-valued constant to the name list must go through the same
`_stable_repr` path, not a bare `repr()`.
```

## Notes for successor

- 1 file, 9 comments + 1 docstring — matches the measured state exactly. All 3 comment blocks are standalone, each 3 lines long, none trailing/inline.
- No load-bearing docstring: grepped `__doc__` — zero hits, no `argparse` in this file. Docstring deleted outright.
- **Run directly** (safe): this script is a pure read-only harness — imports `src.constants`/`src.colors`/`src.core.modes`/`src.pane_error_log` via `importlib`, reads a fixed list of 44 names via `getattr`, hashes `{name: repr(value)}`, prints one `HASH:` line. No file writes, no subprocess, no mutation of any kind.
- Verification: ran twice before the edit (confirmed the hash is stable across separate process runs — the file's own docstring/comments already document why: `_stable_repr` sorts `(frozen)set` values before `repr()`-ing them, specifically to neutralize `PYTHONHASHSEED`-driven `repr(frozenset(...))` ordering, which would otherwise make even an unmodified run's hash non-reproducible). Then ran once more after the comment/docstring strip — `HASH:` line identical to both pre-edit runs.
- DOCS.md rewrite: the `## Gotchas` section (the `PYTHONHASHSEED`/`frozenset` non-determinism finding and the `_stable_repr` mitigation) has no home in the new fixed format, moved here in full — this is exactly the fact this session independently re-confirmed empirically before editing, so treat it as verified twice over, not just inherited prose.
