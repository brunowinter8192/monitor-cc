# dev/pipeline/

## Role
Measurement suite for core monitor pipeline characteristics (memory growth, filesystem call cost,
parsing overhead, message-type coverage) that fed early data-source and core-loop design decisions.
One subdirectory per measured aspect; each holds a single standalone script. Touch when re-measuring
one of these aspects against a changed pipeline; not a regression-guard suite.

## Flow
Each script scans real session JSONL files under the user's Claude Code projects directory (or a
proxy log under src/logs for `format_stability/`), measures its one aspect, and writes a timestamped
Markdown report.

## Modules

### memory_profile/01_cache_growth.py (114 LOC)

**Purpose:** Measures `tool_use_cache`/`buffered_subagent_calls` growth over a session by replaying
its JSONL lines and checkpointing container sizes at a fixed interval.
**Reads:** the newest session JSONL under the user's Claude Code projects directory.
**Writes:** a report to a subdirectory it creates next to itself at run time (see Gotchas for the
current on-disk report location).
**Called by:** none — manual, run via `python3 dev/pipeline/memory_profile/01_cache_growth.py`.
**Calls out:** none — currently broken (see Gotchas).

---

### io_profile/01_poll_cycle_cost.py (164 LOC)

**Purpose:** Counts filesystem calls (`stat`, `iterdir`, `glob`) per poll cycle by monkeypatching
`Path`'s methods around a call to `find_active_sessions`, averaged over 10 cycles.
**Reads:** live filesystem state under the user's Claude Code projects directory, via
`find_active_sessions`.
**Writes:** a report to a subdirectory it creates next to itself at run time (see Gotchas for the
current on-disk report location).
**Called by:** none — manual, run via `python3 dev/pipeline/io_profile/01_poll_cycle_cost.py`.
**Calls out:** `src.session_finder` (`find_active_sessions`).

---

### parsing_profile/01_multipass_cost.py (139 LOC)

**Purpose:** Measures per-extract-function time and multi-pass overhead by timing each session-JSONL
extraction function over 10 runs against the newest session JSONL.
**Reads:** the newest session JSONL under the user's Claude Code projects directory.
**Writes:** a report to a subdirectory it creates next to itself at run time (see Gotchas for the
current on-disk report location).
**Called by:** none — manual, run via `python3 dev/pipeline/parsing_profile/01_multipass_cost.py`.
**Calls out:** none — currently broken (see Gotchas).

---

### format_stability/01_unknown_types.py (198 LOC)

**Purpose:** Scans all session JSONL files for top-level and content-block `type` values not in the
script's own known-type sets, to catch new message shapes early.
**Reads:** all session JSONL files under the user's Claude Code projects directory.
**Writes:** a report to a subdirectory it creates next to itself at run time (see Gotchas for the
current on-disk report location).
**Called by:** none — manual, run via `python3 dev/pipeline/format_stability/01_unknown_types.py`.
**Calls out:** none — pure stdlib, no `src/` imports.

---

## Gotchas
- `memory_profile/01_cache_growth.py` and `parsing_profile/01_multipass_cost.py` both import from a
  flat `jsonl_parser` module path under `src`, which no longer exists — the module now lives inside
  `src/jsonl/`. Both scripts raise `ModuleNotFoundError` on the current tree.
- All four scripts define their own `REPORTS_DIR` as a `01_reports` subdirectory of their own folder
  (created on first run), but the reports actually present on disk today live under each folder's
  `md/` subdirectory instead — the report path in the code has drifted from where past reports were
  kept. A fresh run creates and writes to `01_reports`, not `md`.
- Each script's usage/CLI is documented in `process-docs/pipeline/`, referenced from the original
  design decisions these measurements fed.
