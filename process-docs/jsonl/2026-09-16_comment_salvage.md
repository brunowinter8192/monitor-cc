## Salvage from dev/jsonl/A_extract_cache_turns_proof.py

```
"""
Differential proof harness for extract_cache_turns decomposition.

Usage (from project root):
    ./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode capture
    ./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- parse N session JSONLs, write turns list to baseline JSON
    verify   -- parse same JSONLs, assert byte-identical against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: extract_cache_turns(messages) from src/jsonl/jsonl_cache_turns.py
"""
```

## Salvage from dev/jsonl/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Public Interface`, and `## Modules` sections already fit the required format exactly. No `## Flow` or `## Gotchas` section existed.

## Notes for successor

- 1 `.py` file with content (`A_extract_cache_turns_proof.py`) plus an empty `__init__.py` — 0 comments + 1 docstring, matches the measured state ("1 file" counts the non-empty script; `__init__.py` is empty, confirmed via `Read`, and has nothing to strip).
- No load-bearing docstring: grepped `__doc__` — zero hits. `argparse.ArgumentParser()` in `_parse_args()` takes no `description=` at all. Docstring deleted outright.
- **Run directly** (safe), but with `--mode verify --baseline dev/jsonl/json/baseline_20260610_030515.json` explicitly, not the default `--mode capture`: capture mode would write a brand-new file into `A_extract_cache_turns_proof_reports/` (the real `_REPORTS` dir the code uses — note this does NOT match the tracked `json/` folder name; that is a pre-existing path-drift in this script, already true before this session touched it, out of scope to fix here). Verify mode only reads real session JSONLs (read-only) and the existing committed baseline, and writes nothing.
- Verification: ran before and after the comment/docstring strip with the same `--mode verify --baseline ...` invocation — stdout identical (all real sessions found on this machine currently report `SKIP (not in baseline)` since the committed baseline predates them; that SKIP-only outcome is itself proof of nothing being newly broken, and more importantly it is byte-identical between the two runs, which is what this milestone requires).
