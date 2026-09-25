# dev/jsonl/

## Role
Differential-proof harness for `src/jsonl/` module decompositions: captures baseline output from real session JSONLs and verifies byte-identical results after a refactor, plus a reader test.

## Public Interface
`__init__.py` is empty; no package exports. Each script is run directly.

## Flow
The proof script loads recent real session JSONLs, runs the cache-turn extraction and either writes a baseline or compares against one. The reader test runs parallel strands against temp files.

## Modules

### A_extract_cache_turns_proof.py (107 LOC)

**Purpose:** Captures and verifies byte-identical cache-turn extraction output across real session JSONLs.
**Reads:** real session JSONLs under the user's Claude projects directory.
**Writes:** `json/baseline_<timestamp>.json`.
**Called by:** none; run manually in capture then verify mode.
**Calls out:** `src.jsonl.jsonl_cache_turns`.

---

### test_jsonl_reader.py (109 LOC)

**Purpose:** Five parallel strands proving the shared JSONL reader: partial tail kept, interior corruption raises, downstream readers follow it.
**Reads:** temp files only; an env var selects the source tree so the file can run against an older tree.
**Writes:** stdout only (pass or fail per strand).
**Called by:** none; manual test.
**Calls out:** `src.jsonl`, `src.panes.cache_turns`, `src.gpu_pane.errors`.

---

## State
None beyond the baseline files the proof script writes under its own reports directory.
