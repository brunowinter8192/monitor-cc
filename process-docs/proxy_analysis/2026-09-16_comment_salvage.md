# 2026-09-16 — Comment/docstring salvage for dev/proxy_analysis/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/proxy_analysis/` into conformance with the project's three-marker comment
standard. This area's `.py` files are `01_session_summary.py` (the counted file) and an empty
`__init__.py` (0 lines, no content to salvage or strip). Zero `__doc__`/`argparse.description=__doc__`
hits — the argparse `description=` in this file is a plain string literal, not a docstring, so
nothing was load-bearing.

**Confirmed safe and run for real.** `01_session_summary.py` only reads a JSONL log and prints an
ANSI-colored report to stdout — no desktop interaction. Its own DOCS.md documents that the flat
log schema it expects isn't produced by any current `src/` writer. Built a small synthetic
`api_requests_test1.jsonl` fixture matching the expected schema (`total_input_chars`,
`diff_from_prev`, `message_count`, `cache_breakpoints`, `model`, `timestamp`) under a temp
`MONITOR_CC_ROOT`, ran `01_session_summary.py test1` before and after the edit — stdout diffed
byte-for-byte identical (see the completion checklist in the task response for the result).

---

## Salvage from dev/proxy_analysis/01_session_summary.py

Was line 35 (above `_find_logs_dir`):
```
# Locate src/logs/ — checks MONITOR_CC_ROOT env, then script-relative, then cwd-relative
```

Was line 45 (above `_resolve_log_file`):
```
# Resolve log file from session_id or auto-discover most recent
```

Was line 64 (above `_load_entries`):
```
# Load and parse all JSONL entries from file
```

Was line 78 (above `_to_local`):
```
# Convert UTC ISO timestamp string to local time display string
```

Was line 87 (above `_fmt_chars`):
```
# Format chars count as human-readable (5c, 114k, 2.1M)
```

Was line 96 (above `_short_model`):
```
# Shorten model name for display (claude-opus-4-6 → opus-4-6)
```

Was line 101 (above `_is_non_opus`):
```
# Return True if model is not an opus variant
```

Was line 106 (above `_print_overview`):
```
# Print section 1: overview
```

Was line 126 (above `_print_anomalies`):
```
# Print section 2: anomalies
```

Was line 174 (above `_print_anomaly_section`):
```
# Print a named anomaly group with formatted lines
```

Was line 184 (above `_fmt_haiku`):
```
# Format a non-opus call anomaly line
```

Was line 190 (above `_fmt_rebuild`):
```
# Format a cache rebuild anomaly line
```

Was line 206 (above `_fmt_compression`):
```
# Format a compression event anomaly line
```

Was line 212 (above `_fmt_jump`):
```
# Format a large input jump anomaly line
```

Was line 221 (above `_print_timeline`):
```
# Print section 3: compact one-line-per-request timeline
```

## Salvage from dev/proxy_analysis/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas

**The log schema this script expects is not produced by any current `src/` writer.** It reads a
flat JSONL file whose entries carry top-level `total_input_chars`, `diff_from_prev`,
`message_count`, and `cache_breakpoints` keys — none of these appear in `src/` as log-entry fields
(`cache_breakpoints` elsewhere in `src/proxy/addon.py` is an outgoing request-payload field, not a
log key). The current logger (`src/proxy/addon_dual_log.py`) writes the six-stream split
(`_original`/`_forwarded`/`_stripped`/`_injected`/`_response`/`_errors`) under
`src/logs/dual_log/`, not a flat `api_requests_<id>.jsonl` entry list. Running this script against
a real `src/logs/` tree will find no matching file or parse entries missing every field it reads,
printing zeros/blanks rather than raising.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
