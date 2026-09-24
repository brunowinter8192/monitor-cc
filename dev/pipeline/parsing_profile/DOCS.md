# dev/pipeline/parsing_profile/

## Role
Times each session-JSONL extract function to measure multi-pass parsing overhead. Touch only when re-measuring parsing cost against a changed pipeline; not a regression suite.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/pipeline/parsing_profile/01_multipass_cost.py`.

## Flow
The script scans real session JSONL files under the user's Claude Code projects directory and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Modules

### 01_multipass_cost.py (133 LOC)

**Purpose:** Times each session-JSONL extract function over repeated runs on the newest session to measure multi-pass parsing overhead.
**Reads:** the newest session JSONL under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** `src.jsonl_parser`, a broken import: the module now lives under `src/jsonl/`.

---

## State
None.
