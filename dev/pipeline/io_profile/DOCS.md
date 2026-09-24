# dev/pipeline/io_profile/

## Role
Counts filesystem calls per poll cycle of the session finder. Touch only when re-measuring poll cost against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/pipeline/io_profile/01_poll_cycle_cost.py`.

## Flow
The script scans real session JSONL files under the user's Claude Code projects directory and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Modules

### 01_poll_cycle_cost.py (156 LOC)

**Purpose:** Counts filesystem calls per poll cycle by patching path methods around the session finder, averaged over repeated cycles.
**Reads:** live filesystem state under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.session_finder`.

---

## State
None.
