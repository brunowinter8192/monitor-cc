# dev/cache/

## Role
Persists a durable, deduplicated extraction of every Bash tool call in the recorded dual-log corpus whose command matches a known file-content-modification form. Touch to regenerate after dual-log rotation or a classification change. Do not touch `dev/cache/samples/`; an unrelated earlier measurement owns it.

## Public Interface
No `__init__.py`. Entry point: `./venv/bin/python dev/cache/extract_bash_file_mods.py`.

## Flow
Streams every original dual-log file of the main checkout, finds Bash tool-use blocks, deduplicates per session, matches each command against the shared classification in `src/constants.py` and writes one JSON record per match to a new run-stamped file under `dev/cache/jsonl/`. No aggregation.

## Modules

### extract_bash_file_mods.py (115 LOC)

**Purpose:** Extracts and persists every Bash tool call matching a file-content-modification form, verbatim, with enough identity to find it again.
**Reads:** every `*_original.jsonl` under the main checkout's dual-log directory (this worktree carries no logs).
**Writes:** `dev/cache/jsonl/bash_file_mods_<UTC-timestamp>.jsonl`, one new file per run, never an existing one.
**Called by:** none; manual, re-run after rotation or a classification change.
**Calls out:** `src.constants`.

---

## State
`dev/cache/jsonl/` accumulates one snapshot per run named by its UTC start time; existing files are never overwritten. There is no canonical current file; the newest is the lexicographically last name. Matching limits, the excluded command family and the exclusive-create tripwire are in process-docs.
