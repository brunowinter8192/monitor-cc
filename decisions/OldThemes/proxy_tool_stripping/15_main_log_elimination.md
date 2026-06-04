# Main Log Elimination — Feasibility Probe (2026-06-04)

## What We Did

Built `dev/proxy_dual_log/main_log_elimination_probe.py` to answer whether the dual-log quartet
(`_original`, `_forwarded`, `_stripped`, `_injected`) can losslessly replace the main log
(`api_requests_<id>.jsonl`) as the monitor's read-side data source.

Ran against session `opus_monitor_cc_1780602018` (47 requests, 2 model families: haiku + opus).

## What We Found

### A — Forwarded reconstruction content: LOSSLESS

After stripping `cache_control` from both sides and applying `_normalize_msg_shape_for_hash`
(collapses single-text-block user messages to plain string — same normalization the delta-hash
uses), the reconstructed `{system, tools, messages}` matched the main-log `raw_payload` exactly
across all 47 requests (47/47 per section). No content divergence after normalization.

Matching strategy: positional. The quartet logs carry empty `request_id` (CC sends no
`x-request-id` header; main log falls back to UUID4, quartet uses `""`). Both logs are written
by the same serial `request()` hook in identical order, so line-N correspondence is exact.

### A — BP:N counter: NOT derivable from quartet

Main log `cache_breakpoints` = message-index list computed from `modified_payload` **before**
`_strip_all_cache_control` + `_set_cache_breakpoints` (i.e., CC's original markers on the
pre-ops payload). `_forwarded` carries the **post-ops** payload where the proxy has replaced
all markers with its own per-message breakpoints. These accumulate monotonically (3→46 over the
session as new messages receive cache markers). The pre-ops count (always 3 for opus in this
session — the 3 static system-block anchors CC sends) cannot be reconstructed from the
post-ops forwarded payload. `sent_meta` (which carries `sent_cache_breakpoints`) is also a main
log record, not in the quartet.

**Migration consequence:** the `BP:N` header counter must be **dropped** from the proxy-pane
row header in the migration. There is no accurate equivalent in the quartet.

### A — Missing top-level fields: 2 must-add, 6 irrelevant

`_build_forwarded_delta` only delta-encodes `{system, tools, messages}`. Raw payload top-level
fields not in the forwarded delta:

| Field | Action | Reason |
|---|---|---|
| `max_tokens` | **MUST-ADD** | proxy pane header `think:Nk` via `_fmt_thinking_budget(max_tokens)` |
| `output_config` | **MUST-ADD** | proxy pane header `eff:X` via `output_config.get('effort')` |
| `temperature` | drop | metadata-pane-only — pane being deleted |
| `top_p` / `top_k` | drop | metadata-pane-only |
| `tool_choice` | drop | metadata-pane-only |
| `thinking` | drop | metadata-pane-only; proxy pane uses `max_tokens` directly |
| `context_management` | drop | metadata-pane-only |
| `metadata` (req metadata) | drop | metadata-pane-only |
| `diagnostics` | drop | metadata-pane-only |
| `stream` | drop | metadata-pane-only |

### B — Tool error extraction: EXACT MATCH

Scanning `_original` payloads for `is_error=True` tool_result blocks, deduped by `tool_use_id`:
1 unique error extracted. `tool_errors.jsonl` has exactly 1 entry for this session, same
`tool_use_id` (`toolu_01LTWsUkWMtknDKYSpQGykrA`). Same error appeared in entries 29–38 (10 raw
occurrences) because cumulative history; dedup-by-ID collapses to 1.

The current write path (`warnings_scan` reads main-log summaries → `append_tool_errors`) can be
migrated to read from `_original` payloads using the same `tool_use_id` dedup without
information loss.

## Dev Scripts Used

- `dev/proxy_dual_log/main_log_elimination_probe.py` — probe script
- `dev/proxy_dual_log/main_log_elimination_probe_reports/20260604.md` — full per-request table + classification

## Decision / Next

Feasibility proven. Migration prerequisites before `src/` changes:

1. Add `max_tokens` and `output_config` to `_build_forwarded_delta` write-side (2-field addition
   to the entry dict in `src/proxy/logging.py`).
2. Remove `BP:N` counter from proxy-pane row header (`render_turn.py`).
3. Migrate `parser.py` read path from main log to `_forwarded` accumulation.
4. Migrate `warnings_scan` / `append_tool_errors` to read from `_original`.

No blocking unknowns. The `_stripped` / `_injected` logs (for overlay rendering) are already
read from the quartet — that path is proven and production-active.
