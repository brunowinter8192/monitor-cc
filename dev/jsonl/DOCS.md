# dev/jsonl/

## Role

Differential-proof harness for `src/jsonl/` module decompositions. Captures baseline output from
real session JSONLs and verifies byte-identical results after a refactor.

## Public Interface

`__init__.py` is empty — no package-level exports; each script is run directly.

## Modules

### A_extract_cache_turns_proof.py (116 LOC)

**Purpose:** Differential-proof harness for `extract_cache_turns` — calls
`extract_cache_turns(messages)` on 10 real Monitor_CC session JSONLs (most-recent by mtime),
serializes the full turns list as JSON, and verifies byte-identical output against a captured
baseline.
**Reads:** real session JSONLs under `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/`.
**Writes:** `json/baseline_<timestamp>.json` (`{session_stem: serialized_turns}` for 10 sessions).
**Called by:** none — run manually (`--mode capture` then `--mode verify [--baseline PATH]`).
**Calls out:** `src.jsonl.jsonl_cache_turns` (`extract_cache_turns`).
