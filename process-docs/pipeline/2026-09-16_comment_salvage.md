## Salvage from dev/pipeline/format_stability/01_unknown_types.py

```
# Find all JSONL files in ~/.claude/projects/
# Scan all files, collect message type counts, content block types, unknowns, versions
# Extract content block types from a single message into the counter
# Get content blocks list from a message (handles assistant/user and progress nesting)
# Collect version info from result-type messages or other known fields
# Write MD report and return path
# Compute known-type coverage percentages for top-level types and content block types
```

## Salvage from dev/pipeline/io_profile/01_poll_cycle_cost.py

```
# Capture originals before any patching
# Count project directories in ~/.claude/projects
# Count all JSONL files in ~/.claude/projects
# Run N poll cycles with call counting and timing, return stats dict
# Compute mean/stdev/min/max for a list of numbers
# Format a stats dict row for the report table
# Write MD report and return path
```

## Salvage from dev/pipeline/memory_profile/01_cache_growth.py

```
# Find the newest JSONL file across all project dirs
# Read all lines from file as list of strings
# Feed lines through parser in batches and snapshot cache size at each checkpoint
# Write MD report and return path
```

## Salvage from dev/pipeline/parsing_profile/01_multipass_cost.py

```
# Find the newest JSONL file across all project dirs
# Read all lines from file as list of strings
# Count message types from parsed messages
# Time each extract function N_RUNS times, return per-function stats in microseconds
# Write MD report and return path
```

## Salvage from dev/pipeline/DOCS.md

```
## Gotchas
- `memory_profile/01_cache_growth.py` and `parsing_profile/01_multipass_cost.py` both import from a
  flat `jsonl_parser` module path under `src`, which no longer exists — the module now lives inside
  `src/jsonl/`. Both scripts raise `ModuleNotFoundError` on the current tree.
- All four scripts define their own `REPORTS_DIR` as a `01_reports` subdirectory of their own folder
  (created on first run), but the reports actually present on disk today live under each folder's
  `md/` subdirectory instead — the report path in the code has drifted from where past reports were
  kept. A fresh run creates and writes to `01_reports`, not `md`.
- Each script's usage/CLI is documented in `process-docs/pipeline/`, referenced from the original
  design decisions these measurements fed.
```

## Notes for successor

- 4 files, 23 comments total, 0 docstrings, 0 load-bearing (`__doc__`/`argparse` grep came back empty). All comments above are one-line function-purpose comments directly preceding a `def`; none were inline trailing comments.
- `memory_profile/01_cache_growth.py` and `parsing_profile/01_multipass_cost.py` import `from src.jsonl_parser import ...`. That module does not exist at that path — it now lives at `src/jsonl/jsonl_parser.py`. Both scripts raise `ModuleNotFoundError: No module named 'src.jsonl_parser'` at import time, unchanged before and after this milestone's comment/docstring removal. Do not fix this import; it is out of scope.
- All 4 scripts default `REPORTS_DIR = Path(__file__).parent / '01_reports'`, which does not exist in the tree (`md/` is the tracked folder actually holding old reports, per the Gotchas above). Running the two working scripts creates a `01_reports/` dir as a side effect; that dir was deleted by name after verification, never via wildcard.
- Behavior-unchanged proof for this milestone: ran each script's real `main()` (for the 2 that import cleanly) once before comment removal and once after, redirected stdout to files under `/tmp/`, and diffed. Diff was empty except for the embedded timestamp in the printed report path, which is expected nondeterminism (timestamp granularity is one second). Also diffed the two ModuleNotFoundError tracebacks (before/after) for the two broken scripts — identical apart from line numbers pointing at the same `from src.jsonl_parser import` line, which did not move.
- DOCS.md rewrite: the `## Gotchas` section has no home in the new fixed format (Role / Public Interface / Flow / Modules / State), so it moved here in full. The `State` section of the new DOCS.md is intentionally short — these scripts own no shared/mutated state beyond their own module-level `REPORTS_DIR`/`N_*` constants and local monkeypatch of `Path` methods in `io_profile/01_poll_cycle_cost.py` (patched then restored within the same function call, never left mutated after `main()` returns).
