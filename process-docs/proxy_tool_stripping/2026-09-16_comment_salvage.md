# 2026-09-16 — Comment/docstring salvage for dev/proxy_tool_stripping/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/proxy_tool_stripping/` (2 `.py` files) into conformance with the project's
three-marker comment standard. Zero `__doc__`/`argparse` hits — both docstrings found here (one
per file) were not load-bearing and deleted outright.

**`probe_trailing_message_shapes.py` has a genuine, pre-existing crash unrelated to this
milestone — found while verifying, NOT fixed here (out of scope; comments/docstrings only).** Its
3 hardcoded corpus stems under `src/logs/dual_log/` in the main repo (`api_requests_opus_wise2627_
1788612045`, `api_requests_opus_websearch_1788611995`, `api_requests_opus_monitor_cc_1788611156`)
are all rotated/missing — confirmed on the filesystem before running. Running it raises
`FileNotFoundError` on the first stem immediately inside `_all_stripped_texts`'s `open(path, ...)`
call. Ran it before and after the edit: identical `FileNotFoundError` on the identical first
missing path both times (verdict only diffed, full traceback not printed into context per the
economy requirement — see the completion checklist in the task response for the exact result).

`tests/test_whole_stripped_tool_expand.py` is fully synthetic and safe — ran before and after,
stdout diffed byte-for-byte identical (`37/37 passed`, `ALL PASS` both times).

---

## Salvage from dev/proxy_tool_stripping/probe_trailing_message_shapes.py

Module docstring (was lines 1-14):
```
Measures every distinct SHAPE of a stripped message text that ends with the total_tokens tag,
across the three current `_stripped.jsonl` dual-logs. Pure text-shape measurement — reads raw
JSONL and applies regex only, no src/ imports needed.

For each line's `messages_delta` ({msg_idx: {blk_idx: [stripped_text, ...]}}), every individual
stripped text string ending with `<total_tokens>\d+ tokens left</total_tokens>` (allowing
trailing whitespace only) is collected, then normalized by replacing the digit run inside the tag
with `N` — so two occurrences differing only in the token count collapse to the same shape. Counts
are reported per distinct normalized shape, per session.

Usage (from project root):
    python3 dev/proxy_tool_stripping/probe_trailing_message_shapes.py
```

Was lines 31-33 (above `_ENDS_WITH_TAG_RE`):
```
# Ends-with-tag detector: the tag itself, optionally followed only by trailing whitespace, anchored
# to the END of the string — a marker embedded mid-text (quoted in a tool_result, etc.) does NOT
# qualify, matching the same anchoring philosophy _TOTAL_TOKENS_NUKE_RE already uses for the bare case.
```

Was line 41 (above `_all_stripped_texts`):
```
# All individual stripped-text strings across every message/block of one _stripped.jsonl file
```

Was lines 63-65 (above `_normalize`):
```
# Normalize one qualifying text: replace the tag's digit run with 'N'. Whitespace outside the tag
# (leading/trailing on the whole string) is preserved as part of the shape — a nudge-only variant
# and a whitespace-padded bare-tag variant are meaningfully different shapes.
```

## Salvage from dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py

Shebang (line 1, stays — not a comment per the standard):
```
#!/usr/bin/env python3
```

Module docstring (was lines 2-13, immediately after the shebang):
```
Unit tests for the whole-stripped tool row expand feature (Milestone 2, 2026-09).

Coverage:
  - render_sections._render_whole_stripped_tool: collapsed-row bytes/key shape, expanded body with
    a resolved tool_def (description + params), expanded fallback when tool_def is None.
  - render_sections.render_tools: use_dual whole-stripped loop wires _original_tools_by_name
    through to the new function; forwarded-tool rows and every other section are untouched.
  - parser._find_original_log_path / accumulate_original_tools: path derivation, per-family latest-
    snapshot overwrite behavior, missing-file no-op.

Run: python3 dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py
```

Was line 39 (section divider comment, above the `_render_whole_stripped_tool` test group):
```
# ── _render_whole_stripped_tool ────────────────────────────────────────────────
```

Was line 88 (section divider comment, above the `render_tools` integration test group):
```
# ── render_tools integration ────────────────────────────────────────────────────
```

Was line 124, trailing on a dict-literal line (inside `t06_whole_stripped_row_collapsed_falls_back_when_no_original_available`):
```
        original_tools_by_name={},  # simulates worker-pane path: never attached / not yet resolved
```
(the comment token itself is `# simulates worker-pane path: never attached / not yet resolved`)

Was line 135 (above `t07_forwarded_tool_row_unaffected`'s body, first statement comment):
```
    # Same forwarded-tool rendering path as before this milestone — no whole-stripped tools at all.
```

Was line 149 (section divider comment, above the parser test group):
```
# ── parser: _find_original_log_path / accumulate_original_tools ────────────────
```

Was line 168, trailing on a dict-literal line (inside `t10_accumulate_original_tools_latest_snapshot_per_family`):
```
            {'model': 'claude-haiku-4-5', 'payload': {'messages': []}},  # no tools key at all
```
(the comment token itself is `# no tools key at all`)

Was line 185 (inside `t10_accumulate_original_tools_latest_snapshot_per_family`, above the incremental-append block):
```
        # Incremental: a new line appended, read from pos, should merge onto the SAME dict object
```

## Salvage from dev/proxy_tool_stripping/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas
- The whole-stripped-tool-expand feature's byte-identity regression reuses
  `dev/proxy_dual_log/A_render_refactor_proof.py` rather than a harness in this directory — its
  current baseline lives at `dev/proxy_dual_log/A_render_refactor_proof_reports/baseline_20260905.json`.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
