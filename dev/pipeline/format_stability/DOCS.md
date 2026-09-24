# dev/pipeline/format_stability/

## Role
Scans all session JSONL files for top-level and content-block types outside a known set. Touch only when re-checking the session format against a new Claude Code version; not a regression suite.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/pipeline/format_stability/01_unknown_types.py`.

## Flow
The script scans real session JSONL files under the user's Claude Code projects directory and writes one timestamped Markdown report to a `01_reports/` directory it creates beside itself.

## Modules

### 01_unknown_types.py (236 LOC)

**Purpose:** Scans all session JSONL files for top-level and content-block types outside the script's own known-type sets.
**Reads:** all session JSONL files under the Claude projects directory.
**Writes:** a timestamped report under its own `01_reports/`.
**Called by:** none. Dead code by import graph; run manually.
**Calls out:** none; stdlib only.

---

## State
None.
