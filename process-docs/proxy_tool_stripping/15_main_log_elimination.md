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

**(a) Sidecar/turn-grouping + request numbering: FIXED (2026-06)**

Root cause confirmed: the `#N` trigger in `render_turn.py` was `entry_idx == 0 or bp_len >= 1`
where `bp_len = len(entry.get('cache_breakpoints', []))`. After Stage 2, `cache_breakpoints` is
hardcoded `[]` for every forwarded entry — `bp_len >= 1` never fired; only the very first global
entry (`entry_idx==0`) got `#N`. All others fell into `#N.M`. Additionally, `format.py:112`
reseeded `opus_req_num = sum(api_calls...)` per turn-group, producing `#0` for the first turn
and gaps. The sidecar gate was haiku-only (`model_short == 'haiku'`), so non-haiku zero-context
sidecars would have received real `#N` labels.

**Fixes applied (two commits on req-numbering branch):**

1. **Trigger** (`render_turn.py` + `format.py` no-turns fallback): replaced `bp_len` / `entry_idx`
   check with `(entry.get('diff_from_prev') or {}).get('messages_added', 1) > 0`. A fresh
   conversation turn adds messages (`messages_added > 0`) → `#N`; retry/abort re-send of the same
   list (`messages_added == 0`) → `#N.M`. Default `1` (key absent) treats old entries as fresh.
   Pattern `or {}` matches codebase convention in `render_messages.py` — guards against
   `diff_from_prev = None` from JSONL null deserialization.

2. **Continuous counter** (`format.py`): removed `opus_req_num = sum(api_calls...)` reseeding;
   `opus_req_num` now threads uninterrupted through `render_turn_expanded`'s return value.

3. **Sidecar gate** (`render_turn.py` + `format.py`): `_is_standalone_entry(entry)` replaces
   haiku-only check. Haiku → `'H'`; non-haiku sidecar (`sys_chars==0 AND tools_chars==0`) → `'S'`.
   Neither increments `opus_req_num`.

**Verification (live log `opus_monitor_cc_1780670328`, 40 entries):**
- Haiku entries (idx 0-1) → `'H'`
- Opus entries (idx 2-39) → `#1`…`#38`, no gaps, no sub-numbers
- Synthetic retry (messages_added=0): `#1` → `#1.1` → `#2` ✓
- Synthetic non-haiku sidecar (sonnet, sys=0, tools=0): label `'S'`, counter unchanged ✓

**(b) SR/TN header badges (RESOLVED):** Re-sourced via `flow_id` join on the `_stripped`/`_injected` dual-log `fn_map`. `accumulate_dual_log` maintains `_fns_by_flow_id: {flow_id → set(fn_names)}` per family (strip + inject separately), cleared in-place on `is_first`; appends `set(fn_map.values())` keyed by `flow_id` per line. Forwarded entries carry `flow_id` (mitmproxy UUID4 per-flow). Pane attaches `_strip_fns_lookup` / `_inject_fns_lookup` (references to per-family `_fns_by_flow_id` dicts) to each entry. Render emits a count badge: `{n}strip` (YELLOW) / `{n}inj` (GREEN) on the REQ header, where n = `len(lookup.get(flow_id, set()))`; only non-zero parts shown; both-zero → no badge. `_aggregate_entry_tags` removed entirely. `flow_id` join chosen over positional index: 4xx/5xx responses skip the `_stripped`/`_injected` write in `response()` — positional alignment would break on error responses.

**(c) Stage 3 (write-side removal) not started.**

**(d) Full live-verify on new-format logs pending** — needs proxy restart to produce a fresh
`_forwarded` log that includes the `diff_from_prev`-populated entries end-to-end.

---

### Target: per-function strip/inject warnings (fn_map-driven)

**Direction chosen + implemented:** drop the four aggregate tag badges (SR/TN/PO/ND) and replace with a count badge showing how many distinct strip/inject functions fired per request. COUNT (not named per-function warnings) was built — `{n}strip` (YELLOW) / `{n}inj` (GREEN) on the REQ header.

#### Data already available (verified this session)

`_build_stripped_injected_deltas` (`src/proxy/logging.py`) already attaches
`fn_map: {loc_key → fn_name}` to every `_stripped` and `_injected` log entry. The full
mapping as written today:

| Location | fn_name |
|---|---|
| `sys[2]` | `_apply_system_passes` |
| `sys[3]` | `_strip_sys3` |
| tools | `_strip_unused_tools` / `inject_mcp_tools` / `_strip_tool_descriptions` |
| messages (TN/REJ/NAG/DEF) | `_apply_first_pass` (via `attribute_chunk` → `_MSG_CODE_TO_FN`) |
| messages (SK/CMD/PYR) | `_apply_cumulative_sr_strips` |
| messages (ALL/ENV/SN/FM) | `_apply_final_sr_pass` |
| messages (PP) | `_apply_po_preview_strip` |
| messages (BGK) | `_apply_bg_exit_strip` |
| messages (GL/BD/HP) | git-lock / bd-noise / hook-prefix functions |
| messages (unclassified) | `"unknown"` (attribute_chunk fallback) |
| fields (model/max_tokens/thinking/output_config) | `_inject_model_override` |
| fields (context_management) | `_inject_context_management` |

#### Implementation (DONE)

1. **`accumulate_dual_log` fn_map accumulation** (`src/proxy_display/parser.py`): ✅ — maintains `acc['_fns_by_flow_id']: {flow_id → set(fn_names)}` per family (`_stripped` + `_injected` each), cleared in-place on `is_first`; appends `set(fn_map.values())` keyed by `flow_id` per line.

2. **Render side — count badge** (`render_turn.py` / `render_entry.py`): ✅ — emits `{n}strip` (YELLOW) / `{n}inj` (GREEN) on REQ header where n = `len(lookup.get(flow_id, set()))`. Named per-function warnings NOT implemented — count is the signal. `_aggregate_entry_tags` removed entirely.

3. **`"unknown"` message cases:** not addressed — out of scope for count-badge implementation.

---

## Stage 3 — Write-side Removal (DONE)

### What Was Removed

**proxy/addon.py:**
- Main-log `_write_entry(self.log_file, ...)` call removed from `request()` hook
- `self.log_file`, `self.prev_sent_hashes_by_model`, `self._schema_checked` state removed
- `_build_entry`, `_build_sent_meta`, `_check_payload_schema` imports removed
- Latency tracking removed from `responseheaders()` + `response()` hooks; `responseheaders()` simplified to `flow.response.stream = True` only (`stream=True` is load-bearing — prevents mitmproxy from buffering the full CC response, which would break CC token streaming)
- `request_id` / `timestamp` re-threaded inline (replaces `_build_entry` return values): `mc_request_id = flow.request.headers.get("x-request-id") or str(uuid.uuid4())`; `mc_timestamp` from `datetime.now(timezone.utc)` — both stored on `flow.metadata` for the `_errors` dual-log writer in `request()`
- `api_errors.jsonl` path re-anchored: `self.errors_log_file.parent.parent / "api_errors.jsonl"` (errors_log_file is in `dual_log/`; `.parent.parent` = `src/logs/`)

**proxy/logging.py:**
- `import uuid` removed
- `_build_entry()` deleted (119-LOC main-log entry builder)
- `_count_system_chars()` deleted (helper for `_build_entry`)
- `_build_latency_update()` deleted (19-LOC latency record builder)
- `_summarize_content_for_log()` deleted (16-LOC content summarizer)
- `_compute_diff()` KEPT — re-exported to `cache.py` + `parser.py`
- `_summarize_message` import KEPT — re-exported to `cache.py`

**proxy/hash_meta.py:** deleted entirely — `_compute_sys_block_hashes`, `_compute_tool_hashes`, `_compute_msg_hashes`, `_compute_msg0_block_hashes`, `_compute_drift_report`, `_build_sent_meta` (sent_meta JSONL record builder); zero external callers confirmed.

**proxy/schema_check.py:** deleted entirely — `_check_payload_schema` (schema drift detection on first opus request); zero external callers confirmed.

**core/monitor.py:**
- `_refresh_strip_cache()` function deleted (scanned main log to feed strip data into 0:main pane)
- `_refresh_strip_cache()` call removed from `run_main_loop` poll cycle
- `_strip_proxy_position: int = 0` state removed
- `ingest_proxy_strip_data` import removed

**core/monitor_display.py:**
- `ingest_proxy_strip_data()` deleted (populated `_strip_by_tool_id` / `_strip_prompt_ts_set`)
- `_strip_by_tool_id: dict`, `_strip_prompt_ts_set: set` state removed
- `_format_event_to_lines` tool_call branch: strip overlay removed — `output_data = d['output'] or ''` directly; `highlight_stripped` call removed
- `_format_event_to_lines` user_prompt branch: `strip_badge=False` hardcoded (badge was `[~]` when proxy had stripped msg[0])
- `from ..format.strip_marker import highlight_stripped, build_tool_id_strip_lookup` import removed

**format/strip_marker.py:**
- `get_stripped_data()` deleted
- `build_tool_result_strip_lookup()` deleted
- `build_tool_id_strip_lookup()` deleted
- `highlight_stripped()` KEPT — still used by `panes/warnings_render.py:71`

**proxy_display/parser.py (9 functions deleted):**
- `_enrich_content_tails`, `_lazy_load_messages`, `_extract_raw_payload_fields` (raw-payload field extraction pipeline)
- `_parse_log_file` (main-log JSONL reader with `sent_meta`/`latency_update` merge via `pending_by_rid`)
- `parse_proxy_log` (marker-file lookup + `_parse_log_file` call)
- `scan_worker_logs` (glob worker main-logs, `_parse_log_file` per file)
- `_subprocess_worker`, `_parse_log_file_isolated` (subprocess offload pattern)
- `parse_proxy_log_isolated` (isolated variant of `parse_proxy_log`)
- `import logging`, `KNOWN_PAYLOAD_KEYS`/`KNOWN_CONTENT_BLOCK_TYPES`/`KNOWN_TOOL_DEFINITION_KEYS`/`KNOWN_MESSAGE_ROLES` constants import also removed
- `entry['schema_warnings'] = []` placeholder removed from `_extract_forwarded_fields`
- `find_worker_proxy_log` updated: primary source = `dual_log/api_requests_worker_*_forwarded.jsonl` glob; returns synthetic `logs_dir/stem.jsonl` path (stem = log_id, never opened as file); legacy main-log glob as fallback

**proxy_display/render_entry.py:**
- schema_warnings rendering block deleted (11 lines: header + expand + per-warning lines)

**proxy_display/__init__.py:**
- `parse_proxy_log`, `parse_proxy_log_isolated`, `_parse_log_file`, `_parse_log_file_isolated` removed from imports

**panes/warnings_persist.py:** deleted — `append_tool_errors` no-op stub; zero external callers.
**panes/warnings_scan.py:** deleted — scan stubs; zero external callers.

**log_janitor.py:**
- `tool_errors` LogSpec removed (writer stub, no reader, superseded by `_errors` dual-log)
- `api_requests_opus` LogSpec removed (main log eliminated)
- `api_requests_worker` LogSpec removed (main log eliminated)
- Registry: 12 entries → 10 entries

### Rotation Re-anchor (Block C)

Old anchor: derived surviving `log_id`s from `LOG_DIR/api_requests_opus_*.jsonl` + `api_requests_worker_*.jsonl` main logs. After main-log elimination these globs return empty → dual_log/ would be fully deleted on every proxy start.

New anchor (per-class split, user condition): 
- Phase 1a: rotate `dual_log/api_requests_opus_*_original.jsonl` keep-30
- Phase 1b: rotate `dual_log/api_requests_worker_*_original.jsonl` keep-30
- Phase 2: surviving `log_id`s = union from remaining `_original` files (strip `_original` suffix)
- Phase 3: delete `dual_log/api_requests_*.jsonl` not in surviving set — suffix-stripping loop covers `original/forwarded/stripped/injected/errors`

Pre-existing bug fixed: `_errors` suffix was missing from the strip loop → `_errors` files always deleted (stem never reduced to base log_id). Fixed by adding `errors` to `for sfx in original forwarded stripped injected errors`.

Marker staleness check re-anchored: `$LOG_DIR/dual_log/api_requests_${existing_log_id}_forwarded.jsonl` (was `$LOG_DIR/api_requests_${existing_log_id}.jsonl`). Checks mtime < 60s to decide if existing marker is still live.

### Verification

- Import smoke: `core.monitor` + `proxy_display` + `proxy` packages — clean
- Per-symbol dead-caller grep: 18 symbols at 0 live callers
- `grep '_write_entry(self.log_file'` → 0 hits
- Rotation dry-run on real `dual_log/` data: 206 files retained, 0 deleted (no stale files present)

### Pending Live-Verify (Stage 3) — next session after proxy restart

Requires a fresh monitor-cc proxy restart (new code on dev). Three checks:
1. No new main log written: `ls -lt src/logs/api_requests_*.jsonl` shows NO top-level file growing with a fresh mtime; only `src/logs/dual_log/` grows.
2. Tab 0:main renders tool outputs with NO strip underlays (no coloured highlights), green call/response headers intact, no crash.
3. Tab 1:proxy and Tab 2:workers (worker-proxy via new find_worker_proxy_log dual-log discovery) render normally.

On all green: close the tracking task and sync dev to main.
