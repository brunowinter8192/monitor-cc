# dev/pipeline/

## Role
Standalone measurement scripts that profiled memory growth, filesystem call cost, parsing overhead, and message-type coverage of the core monitor pipeline, feeding early data-source and core-loop design decisions. Touch only when re-measuring one of these aspects against a changed pipeline; this is not a regression-guard suite.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly, e.g. `python3 dev/pipeline/<subdir>/<script>.py`.

## Flow
Each script scans real session JSONL files under the user's Claude Code projects directory (format_stability instead scans all such files, others scan the newest one). Each script measures its own single aspect: cache growth, filesystem call counts, extract-function timing, or type coverage. Each script writes one timestamped Markdown report to a `01_reports/` directory it creates next to itself.

## Modules

### memory_profile/01_cache_growth.py (109 LOC)

**Purpose:** Measures tool-call cache growth across a session's JSONL by replaying it in batches and snapshotting cache size at each checkpoint.
**Reads:** the newest session JSONL under the user's Claude Code projects directory.
**Writes:** a timestamped Markdown report to a `01_reports/` directory it creates next to itself.
**Called by:** none. DEAD CODE by import graph — invoked manually as a script.
**Calls out:** `src.jsonl_parser` — broken import, the module now lives at `src/jsonl/jsonl_parser.py`.

---

### io_profile/01_poll_cycle_cost.py (156 LOC)

**Purpose:** Counts filesystem `stat`/`iterdir`/`glob` calls per poll cycle by monkeypatching `Path` methods around `find_active_sessions`, averaged over 10 cycles.
**Reads:** live filesystem state under the user's Claude Code projects directory, via `find_active_sessions`.
**Writes:** a timestamped Markdown report to a `01_reports/` directory it creates next to itself.
**Called by:** none. DEAD CODE by import graph — invoked manually as a script.
**Calls out:** `src.session_finder` (`find_active_sessions`).

---

### parsing_profile/01_multipass_cost.py (133 LOC)

**Purpose:** Times each session-JSONL extract function over 10 runs against the newest session JSONL to measure multi-pass parsing overhead.
**Reads:** the newest session JSONL under the user's Claude Code projects directory.
**Writes:** a timestamped Markdown report to a `01_reports/` directory it creates next to itself.
**Called by:** none. DEAD CODE by import graph — invoked manually as a script.
**Calls out:** `src.jsonl_parser` — broken import, the module now lives at `src/jsonl/jsonl_parser.py`.

---

### format_stability/01_unknown_types.py (232 LOC)

**Purpose:** Scans all session JSONL files for top-level and content-block type values not in the script's own known-type sets.
**Reads:** all session JSONL files under the user's Claude Code projects directory.
**Writes:** a timestamped Markdown report to a `01_reports/` directory it creates next to itself.
**Called by:** none. DEAD CODE by import graph — invoked manually as a script.
**Calls out:** none — pure stdlib, no `src/` imports.

---

## State
None of these scripts own persistent or shared state. `REPORTS_DIR` and the run-count constants (`N_CYCLES`, `N_RUNS`, `CHECKPOINT_INTERVAL`) are module-level constants read only within their own file. `io_profile/01_poll_cycle_cost.py` monkeypatches `Path.stat`/`iterdir`/`glob` for the duration of `run_cycles()` and restores the originals before returning; nothing outside that function observes the patch.
