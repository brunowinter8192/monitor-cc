# 2026-09-16 — Comment/docstring salvage for dev/tool_use_errors/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/tool_use_errors/` (4 `.py` files) into conformance with the project's
three-marker comment standard. Zero `__doc__`/`argparse` hits anywhere in this area — nothing
load-bearing, no docstrings existed here at all (0 stated and confirmed).

**Confirmed safe and run for real, via monkeypatched constants for determinism.**
`A_error_cluster_audit.py` resolves `MAIN_PROJECT` via `.git` traversal and reads the real main
checkout's `src/logs/tool_errors.jsonl` + `api_requests_*.jsonl` by default — both are live files
under active growth in this environment (multiple real monitor/worker sessions running), so a
plain before/after run against them would not be a clean diff. Instead: imported
`A_error_cluster_audit` as a module (with `dev/tool_use_errors/` added to `sys.path`, matching how
its own sibling imports already expect to be loaded) and monkeypatched its module-level
`TOOL_ERRORS_LOG`/`LOGS_DIR`/`REPORTS_DIR`/`REPORT_DATE` constants to point at a synthetic fixture
(7 `tool_errors.jsonl` entries covering every cluster bucket — hook_prefixed, tool_use_error,
exit_code_0, exit_code_nonzero, rejection, bare_guidance, other — plus a 2-line proxy log carrying
the `stripped_hook_error_prefix` modification marker for the cross-check) and a fixed report
directory, then called `audit_workflow()` directly before and after the edit. The produced report
file diffed byte-for-byte identical (see the completion checklist in the task response for the
result). The three library modules (`error_cluster_extraction.py`, `error_cluster_crosscheck.py`,
`error_cluster_report.py`) are exercised transitively by this same call, since
`A_error_cluster_audit.py` imports and calls all three.

---

## Salvage from dev/tool_use_errors/A_error_cluster_audit.py

Was line 11, trailing on the `MAIN_PROJECT` assignment:
```
MAIN_PROJECT = None  # resolved below
```
(the comment token itself is `# resolved below`)

Was line 14 (above `_resolve_main_project`):
```
# Resolve MAIN_PROJECT at import time via .git file traversal (worktree-aware)
```

Was line 39 (above `audit_workflow`):
```
# Load tool_errors.jsonl → cluster → classify → cross-check via proxy logs → write report
```

## Salvage from dev/tool_use_errors/error_cluster_crosscheck.py

Was line 11 (above `run_cross_check`):
```
# Scan available proxy logs for stripped_hook_error_prefix; return cross-check result dict
```

Was line 26 (above `_scan_proxy_logs_for_strip`):
```
# Find first occurrence of stripped_hook_error_prefix across all available proxy logs
```

Was line 29, trailing on a statement (inside `_scan_proxy_logs_for_strip`):
```
    strip_request_count  = 0  # unique requests with this modification
```
(the comment token itself is `# unique requests with this modification`)

Was line 30, trailing on a statement (same function):
```
    strip_item_count     = 0  # total modification items (one request can strip N messages)
```
(the comment token itself is `# total modification items (one request can strip N messages)`)

Was line 53 (above `_hook_prefixed_stats`):
```
# Hook-prefixed entries: timestamp range + referenced proxy files
```

Was line 61 (inside `_hook_prefixed_stats`, above the predate-check block):
```
    # Determine if all 59 hook_prefixed entries predate the first strip
```

## Salvage from dev/tool_use_errors/error_cluster_extraction.py

Was line 14 (above `load_entries`):
```
# Load all records from tool_errors.jsonl; return list of dicts
```

Was line 20 (above `cluster_entries`):
```
# Assign each entry to exactly one bucket; return dict bucket_name → list of entries
```

## Salvage from dev/tool_use_errors/error_cluster_report.py

Was line 8 (above `_BARE_HOOK_PATTERNS`):
```
# Hook type inference for bare_guidance bucket
```

Was line 27 (above `infer_bare_hook`):
```
# Infer originating hook for a bare_guidance entry text
```

Was line 35 (above `format_report`):
```
# Format the full markdown audit report
```

Was line 239 (above `write_report`):
```
# Write report to REPORTS_DIR/<date>_error_cluster_audit.md; return absolute path
```

## Salvage from dev/tool_use_errors/DOCS.md

No section, subsection, or bullet in the pre-rewrite `DOCS.md` fell outside the mandated format —
it already carried only Role / Flow / Modules (5-field) with no extra subsections and no trailing
Gotchas-style section. Nothing to cut here; this heading exists for completeness of the walk.
