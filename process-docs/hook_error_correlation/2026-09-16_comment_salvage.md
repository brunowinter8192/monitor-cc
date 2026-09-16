## Salvage from dev/hook_error_correlation/analyze.py

```
MAIN_PROJECT = None  # resolved below by _resolve_main_project()
```

```
# Resolve MAIN_PROJECT at import time via .git file traversal
```

```
# Load logs, overlay via proxy lookup, replay active hooks, write report
```

```
# Count all (non-deduplicated) hook errors per hook name
```

```
# Load unique hook errors; return list enriched with hook_name + hook_status
```

```
# Load fire log entries
```

```
# Return status dict for a hook: active / disabled / removed
```

```
# Enrich each error with exact tool_input from proxy; return list with added fields
```

```
# Locate tool_use_id in proxy JSONL raw_payload.messages; return (input_dict, status_str)
```

```
# Classify active hook errors via replay; return Stufe2 entries
```

```
# Hook is active but proxy file missing → can't verify; treat as unverified not stale
```

```
# Build stdin payload JSON for hook subprocess
```

```
# Run hook subprocess with cwd=MAIN_PROJECT; return exit code
```

```
# Write report to file; return path
```

## Salvage from dev/hook_error_correlation/analyze_report.py

```
# Extract the message after the hook path
```

```
# Format a command for display: truncate to 120 chars
```

```
# Format markdown report answering Q1/Q2/Q3 + join analysis
```

## Salvage from dev/hook_error_correlation/DOCS.md

```
## Gotchas

**Hook replay must run with `cwd=MAIN_PROJECT`, not the worktree** — `block_cd_drift` exits 0
(passes) whenever `os.getcwd()` contains `.claude/worktrees/`, which would silently make every
replay look non-blocking regardless of the hook's real logic.
```

## Notes for successor

- 2 files, 17 true comments, 0 docstrings — matches the measured state exactly. Per-file: analyze.py 14 (13 standalone + 1 trailing inline on the `MAIN_PROJECT = None` line), analyze_report.py 3.
- Same trap as the `sleep_pattern_analysis` milestone: `analyze_report.py` has many lines matching `grep "#"` that are NOT comments — they are Markdown heading strings inside `lines = [...]`/`lines.append(...)` literals (e.g. `"## Q1 — Zählung..."`, `"### Stale (kann unter aktueller Config nicht vorkommen)"`). Those are report output content in German and were left untouched. Only the 3 real `#`-token comments (lines 86, 174, 191 in the original file) were removed.
- Zero load-bearing docstrings: grepped `__doc__`, `argparse`, `description=`, `epilog=` across both files — no hits, no docstrings exist at all in this directory (`ast.get_docstring` returned `None` for both modules and every function).
- **Danger, called out by the requester before this milestone started**: `analyze.py`'s real entry point (`analyze_workflow()` / `__main__`) calls `build_stufe2()`, which for every `hook_status == "active"` entry calls `replay_hook()`, which runs the real hook script under `src/hooks/<name>.py` as a subprocess with `cwd=MAIN_PROJECT`. If that hook blocks, the hook itself calls `log_fire()`, which appends to the **production** `src/logs/hook_firing.jsonl`. Do not run `analyze_workflow()` or `main()` end-to-end, on this tree or on any future revisit of this directory — it is not a sandboxed dev script.
- Verification strategy used instead: exercised every function individually with synthetic fixtures under `/tmp/`, comparing pre-edit vs post-edit output byte-for-byte for: `load_raw_counts`, `load_hook_errors`, `load_fires`, `classify_hook_status` (all 3 branches — active/disabled/removed, using real but harmless probe paths since it's pure `os.path.exists` logic), `build_stufe1`, `lookup_command`, `build_replay_payload`, `write_report`, and `build_stufe2` for its two non-replay branches (`status != "active"` and `tool_input is None`). For `build_stufe2`'s active-replay branch, monkeypatched `replay_hook` in the imported module to a stub returning a fixed exit code, so the branching/classification logic (`exit_code == 2` → `current`, `== 0` → `stale:pattern-narrowed`, else `stale:hook-error-{n}`) was proven unchanged without ever invoking a real hook subprocess. `analyze_report.format_report` was exercised directly with synthetic `stufe1`/`stufe2`/`fires`/`raw_counts` data (pure function, no I/O) and diffed pre/post — identical.
- `_resolve_main_project()` runs at import time (module-level `MAIN_PROJECT = _resolve_main_project()`) and only reads `.git`, walking up from the script's own directory — safe, read-only, exercised automatically by every import of `analyze.py` during this verification.
- DOCS.md rewrite: the `## Gotchas` section (the `cwd=MAIN_PROJECT` / `block_cd_drift` warning) has no home in the new fixed format, so it moved here verbatim. It remains true and load-bearing knowledge for anyone re-running or modifying `replay_hook()` — read it before touching that function.
