# dev/pipeline/

## Role
Standalone measurement scripts that profiled memory growth, filesystem call cost, parsing overhead and message-type coverage of the core monitor pipeline, feeding early design decisions. Touch only when re-measuring one aspect against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Each script is its own entry point: `python3 dev/pipeline/<subdir>/<script>.py`.

## Flow
Each script scans real session JSONL files under the user's Claude Code projects directory (one measures all files, the others the newest). Each measures one aspect and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Modules

### memory_profile/01_cache_growth.py (109 LOC)

**Purpose:** Measures tool-call cache growth across a session by replaying it in batches and snapshotting cache size per checkpoint.
**Reads:** the newest session JSONL under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.jsonl_parser`, a broken import: the module now lives under `src/jsonl/`.

---

### io_profile/01_poll_cycle_cost.py (156 LOC)

**Purpose:** Counts filesystem calls per poll cycle by patching path methods around the session finder, averaged over repeated cycles.
**Reads:** live filesystem state under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.session_finder`.

---

### parsing_profile/01_multipass_cost.py (133 LOC)

**Purpose:** Times each session-JSONL extract function over repeated runs on the newest session to measure multi-pass parsing overhead.
**Reads:** the newest session JSONL under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.jsonl_parser`, a broken import: the module now lives under `src/jsonl/`.

---

### format_stability/01_unknown_types.py (232 LOC)

**Purpose:** Scans all session JSONL files for top-level and content-block types outside the script's own known-type sets.
**Reads:** all session JSONL files under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** none; stdlib only.

---

## State
None. The path-method patching in the poll-cost script is restored before its cycle function returns.
