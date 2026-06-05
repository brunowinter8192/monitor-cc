# Main Log Elimination — Feasibility Probe + Stage 2 Implementation

## What We Did (Feasibility Probe, 2026-06-04)

Built `dev/proxy_dual_log/main_log_elimination_probe.py` to answer whether the dual-log quartet
(`_original`, `_forwarded`, `_stripped`, `_injected`) can losslessly replace the main log
(`api_requests_<id>.jsonl`) as the monitor's read-side data source.

Ran against session `opus_monitor_cc_1780602018` (47 entries at probe time; live session — log grew to 118 entries by Stage 2B verification).

## What We Found

### A — Forwarded reconstruction content: LOSSLESS

After stripping `cache_control` from both sides and applying `_normalize_msg_shape_for_hash`
(collapses single-text-block user messages to plain string — same normalization the delta-hash
uses), the reconstructed `{system, tools, messages}` matched the main-log `raw_payload` exactly
across all 47 entries at probe time (47/47 per section). No content divergence after normalization.

**Full-session verification (Stage 2B, readside2 worker):** same session grown to 118 entries by verification time. Re-ran comparison across all 118 positional pairs: system 118/118 ✅, tools 118/118 ✅, messages 118/118 ✅. Zero malformed lines. The 113-entry parser result at 2B probe time was correct — parser consumed to EOF (`new_pos==file_size` asserted); log grew from 113→115 (ground truth) →118 (current) as the session was live.

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

## Decision / Next (after Feasibility Probe)

Feasibility proven. Migration prerequisites before `src/` changes:

1. Add `max_tokens` and `output_config` to `_build_forwarded_delta` write-side (2-field addition
   to the entry dict in `src/proxy/logging.py`).
2. Remove `BP:N` counter from proxy-pane row header (`render_turn.py`).
3. Migrate `parser.py` read path from main log to `_forwarded` accumulation.
4. Migrate `warnings_scan` / `append_tool_errors` to read from `_original`.

No blocking unknowns. The `_stripped` / `_injected` logs (for overlay rendering) are already
read from the quartet — that path is proven and production-active.

---

## Stage 2 Implementation (2026-06, readside2 worker)

### What We Did

Implemented the read-side migration in four stages (2A–2D), each committed separately.

### Stage 2A — BP:N counter + latency badge removal

- `render_turn.py`: removed `BP:N` display from REQ header (`bp_cnt` var and `f"BP:{bp_cnt}"`);
  removed latency badge (`_format_latency` call + `ttfb_ms`/`output_tokens_per_sec`/`n_stalls` fields).
- `render_entry.py`: same removals (no-turns path).
- `format.py`: removed `_format_latency` helper.
- `cache_breakpoints` field retained in entry dicts — still drives `opus_req_num` increment
  logic (whether request gets new `#N` vs sub-number `#N.M`). Not displayed.

### Stage 2B — Parser forwarded-reconstruction core

New functions in `parser.py`:
- `_summarize_fwd_message(msg)` — wraps `_summarize_message`, adds `content_tail` for expand view
- `_dict_to_list_fwd(delta_dict, count)` — expands `{idx_str: elem}` to list of `count` elements
- `_apply_delta_to_list(prev_list, delta_dict, count)` — shallow-copies prev, applies overwrites, resizes
- `_extract_forwarded_fields(fwd_entry, system, tools, message_summaries) -> dict` — builds entry
  dict with all proxy-pane fields; `messages=None` placeholder (assigned by caller from deque window)
- `_parse_forwarded_log(fwd_path, last_pos, acc_by_family) -> (entries, new_pos)` — core parser;
  deque-bounded: only last `PROXY_MESSAGES_KEEP_LAST=10` entries get `messages` populated, earlier
  entries carry `messages=None` (lazy-loadable via `_fwd_req_idx`)
- `_lazy_load_messages_forwarded(entry, fwd_path) -> bool` — replays delta stream from byte 0 to
  target `_fwd_req_idx`, reconstructs messages for a stripped entry
- `find_errors_log_path(project_filter) -> Optional[Path]` — resolves `_errors` dual-log path
- `parse_proxy_log_forwarded(project_filter, last_pos, acc_by_family) -> (entries, new_pos)` —
  public wrapper: resolves fwd_path from marker file, calls `_parse_forwarded_log`, stamps `_source_file`
- `scan_worker_errors_logs(last_positions, project_session_id, min_mtime) -> (records, positions)` —
  globs `dual_log/api_requests_worker_{sid}_*_errors.jsonl`, reads new records per file by byte-pos,
  extracts worker_name from filename stem (mirrors `scan_worker_logs` naming logic)

**Deque-bounded memory model:** replaces the main-log's subprocess isolation (spawn child for
initial parse to bound pymalloc peak). With forwarded reconstruction, `messages` are summaries
(not raw payloads), so peak is lower; the deque cap of 10 further bounds the live set. Entries
outside the window carry `messages=None` and are lazy-loaded via forwarded-stream replay on expand.

### Stage 2C — Pane wiring

- `pane.py`: `parse_proxy_log_forwarded` replaces `parse_proxy_log_isolated`; `_proxy_fwd_pos`+
  `_proxy_acc_fwd` replace `_proxy_pending_by_rid`; lazy-load uses `_lazy_load_messages_forwarded`
  with fwd_path derived from `_proxy_log_path.parent / 'dual_log' / f'{stem}_forwarded.jsonl'`.
- `worker_proxy_pane.py`: `_parse_forwarded_log` called directly with fwd_path derived from
  `find_worker_proxy_log` result. State `_worker_proxy_fwd_pos`+`_worker_proxy_acc_fwd` replace
  `_worker_proxy_pending_by_rid`. Lazy-load same fwd_path derivation pattern.
- Both reset blocks (session-change + time-triggered reparse) reset fwd_pos to 0 + `.clear()` on acc.
- Graceful degrade: `_parse_forwarded_log` returns `([], last_pos)` on missing file.

### Stage 2D — Warnings pane

**Approach chosen:** read `_errors` dual-log directly rather than scanning `_original` payloads.
Rationale: `_errors` log is already written by the proxy write-side (`_build_errors_entries`),
pre-deduped by `tool_use_id`, and covers both main and worker sessions. No need to re-implement
the `is_error=True` scan + dedup in the pane.

**Implementation:**
- `_refresh_warnings_data` reads main session `_errors` log from `_errors_log_pos` (0 per session).
- `scan_worker_errors_logs` globs worker `_errors` logs, filters by `min_mtime=_monitor_start_ts`
  (current-session-only). Worker_name extracted from filename stem.
- `_errors_record_to_display(rec)` converts `{ts, worker, tool_name, tool_use_id, error_full, ...}`
  to the `tool_errors` display dict. `worker_name` from `rec['worker']` (`worker:<name>` prefix) OR
  `_worker_name_from_file` fallback.
- Dropped: `_proxy_log_position`, `_proxy_pending_by_rid`, `_worker_log_positions`, dedup sets
  (`_seen_error_keys`, `_seen_zero_keys`), `zero_results`, `schema_warnings` state.
- `warnings_scan.py`: both functions stubbed (return empty tuple); file kept for import compat.
- `warnings_persist.py`: `append_tool_errors` stub; `tool_errors.jsonl` orphaned.
- `warnings_parse.py`: `_iso_to_float`, `_is_tool_error`, `_is_zero_result_block`,
  `_ZERO_RESULT_PATTERNS`, `_extract_tool_call_details`, `_build_tool_use_id_map`, `_resolve_tool_call`
  dropped (dead after scan removal). `track_unknown_type`, `unknown_type_counts`,
  `format_unknown_type_warning`, `format_warnings_block` retained (used by render + monitor_session).

### Remaining: Stage 3 (not started)

Remove main-log write path from `proxy/addon.py` + `proxy/logging.py`; remove `sent_meta`,
`latency_update`, `schema_warning` record types; remove main-log + tool_errors.jsonl LogSpec
entries from `log_janitor.py`; clean up `warnings_scan.py` / `warnings_persist.py` stubs.

---

## Stage 2E — Render-layer regressions (live-verify, 2026-06)

### What We Found (live-verify after Stage 2 merge)

Three fields consumed by the render layer were never set by `_extract_forwarded_fields`:

| Field | Symptom | Root cause |
|---|---|---|
| `diff_from_prev` | All messages shown as new (no new-vs-old delta) | `render_messages.py` reads `entry['diff_from_prev']`; absent → `fdi=None` → `start=0` → all messages treated as new |
| `modifications` | SR/TN header badges + bucket signals gone | `_aggregate_entry_tags` / `classify_req` consume `modifications`; `_extract_forwarded_fields` sets `modifications=[]` always — the migration removed the field source |
| `cache_breakpoints=[]` always | Everything rendered as sidecar | `_is_standalone_entry` had two `cache_breakpoints==[]`-guarded branches; since bp=[] always for forwarded entries, both fired — real opus REQs classified as sidecars |

### Stage 2E.1 — FIXED (two of three)

**diff_from_prev:** in `_parse_forwarded_log`, capture `prev_messages_for_diff` from
`acc_by_family[family]['messages']` BEFORE updating the accumulator (`None` when `is_first=True`
— proxy-session reset, treat as first-ever request for this family). After computing
`new_summaries`, stamp `entry['diff_from_prev'] = _compute_diff(prev_messages_for_diff,
new_summaries)` (`_compute_diff` imported from `..proxy.logging` — no mitmproxy deps, no circular
imports). Import added to parser.py INFRASTRUCTURE.

**Offline verification (session `opus_monitor_cc_1780602018`):** 20/20 opus entries: reconstructed
`diff_from_prev` (first_diff_index, messages_added, messages_removed) matches the main-log
entries' raw `diff_from_prev` exactly. First entry: fdi=0, added=1 ✓. Subsequent entries: fdi
tracks prev mc, added=2 per turn ✓.

**_is_standalone_entry:** rewrote to content discriminator — drops both `cache_breakpoints`-guarded
branches and the `mc==1` branch entirely. New logic:

```python
def _is_standalone_entry(entry: dict) -> bool:
    sys_chars = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    tools_chars = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    return (
        'haiku' in entry.get('model', '').lower()
        or (sys_chars == 0 and tools_chars == 0)
    )
```

Real main-session opus/sonnet requests always carry the full CC system prompt
(`sys_chars≈130k`) and tool list (`tools_chars≈2k`). CC title/summary and haiku sidecars have
`sys_chars=0` and `tools_chars=0`. Backward-compatible: old main-log real first-REQs had
`bp=[0]` AND `sys_chars>0` — the new `sys_chars>0` guard protects them identically.

**Offline verification (same session):** haiku → standalone=True ✓; opus first-REQ (mc=1,
sys=129422, tools=2269) → standalone=False ✓; opus multi-msg REQ → standalone=False ✓.

### Remaining after 2E.1

**(a) Sidecar/turn-grouping final state:** the everything-sidecar regression is gone and turns
now group. Exact remaining symptom (if any) needs characterization in the next live-verify —
not yet observed in this session.

**(b) SR/TN header badges (#4 — deferred):** `modifications=[]` always means
`_aggregate_entry_tags` / `classify_tags` see no modifications → no badge. Three design
options:
1. Derive a `modifications`-equivalent from the `_stripped_spans` / `_injected_spans` fn_maps
   already attached by `accumulate_dual_log` (re-synthesize the list from span data).
2. Re-source `classify_tags` / `_aggregate_entry_tags` directly from `_stripped_spans` (cleanest
   — eliminates the `modifications` intermediary entirely).
3. Drop the badges like BP:N and the latency badge (display simplification).

**(c) Stage 3 (write-side removal) not started.**

**(d) Full live-verify on new-format logs pending** — needs proxy restart to produce a fresh
`_forwarded` log that includes the `diff_from_prev`-populated entries end-to-end.
