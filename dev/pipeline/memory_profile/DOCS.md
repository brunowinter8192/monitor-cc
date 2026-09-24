# dev/pipeline/memory_profile/

## Role
Measures tool-call cache growth of the monitor pipeline by replaying the newest session in batches. Touch only when re-measuring memory growth against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/pipeline/memory_profile/01_cache_growth.py`.

## Flow
The script scans real session JSONL files under the user's Claude Code projects directory and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Modules

### 01_cache_growth.py (109 LOC)

**Purpose:** Measures tool-call cache growth across a session by replaying it in batches and snapshotting cache size per checkpoint.
**Reads:** the newest session JSONL under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.jsonl_parser`, a broken import: the module now lives under `src/jsonl/`.

---

## State
None.
