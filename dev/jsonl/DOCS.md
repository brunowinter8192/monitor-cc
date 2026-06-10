# dev/jsonl/

## Role

Differential proof harnesses for `src/jsonl/` module decompositions. Captures baseline output from real session JSONLs and verifies byte-identical results after refactoring.

## Modules

### A_extract_cache_turns_proof.py

**Purpose:** Differential proof harness for `extract_cache_turns` decomposition. Calls `extract_cache_turns(messages)` on 10 real Monitor_CC session JSONLs (most-recent by mtime from `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/`), serializes the full turns list as JSON, verifies byte-identical against baseline.

**Usage:**
```bash
# From project root
./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode capture
./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode verify
./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode verify --baseline dev/jsonl/A_extract_cache_turns_proof_reports/baseline_20260610_030515.json
```

**Output:** `A_extract_cache_turns_proof_reports/baseline_<timestamp>.json` — dict of `{session_stem: serialized_turns}` for 10 sessions.
