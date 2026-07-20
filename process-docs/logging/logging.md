# Log Inventory — Monitor_CC

## State as of the main-log-elimination task

### Log Table

| Name | File | Writer | Reader | Purpose | Format | Retention | Janitor Trigger |
|---|---|---|---|---|---|---|---|
| hook_firing | `src/logs/hook_firing.jsonl` | `hooks/*:log_fire` | (debug/analysis) | Hook execution events (PreToolUse / PostToolUse firings) | JSONL (`ts` field, UTC+Z) | 7d ts-records | monitor-24h |
| api_errors | `src/logs/api_errors.jsonl` | `proxy/addon.py:ProxyAddon.response` | (debug/analysis) | 4xx API errors from mitmproxy: status, error body, request URL, request payload | JSONL (`ts` field) | 7d ts-records | monitor-24h |
| api_requests_dual_original | `src/logs/dual_log/api_requests_<log_id>_original.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | (analysis) | Raw CC payload BEFORE modification (pre-apply_modification_rules) | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_forwarded | `src/logs/dual_log/api_requests_<log_id>_forwarded.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `parse_proxy_log_forwarded` / `_parse_forwarded_log` (Stage 2C) | Delta log of the forwarded (post-modification) payload; carries `max_tokens` + `output_config` + `context_management` + `diagnostics` fields (body-field passthrough; Stage 1 addition) | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_stripped | `src/logs/dual_log/api_requests_<log_id>_stripped.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (yellow overlay) | Delta log: what the proxy removed from the original | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_injected | `src/logs/dual_log/api_requests_<log_id>_injected.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (green overlay) | Delta log: what the proxy injected into the forwarded payload | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_errors | `src/logs/dual_log/api_requests_<log_id>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `find_errors_log_path` + `_read_errors_log` (Stage 2D) | Derived tool-error log: `is_error=True` tool_result blocks extracted from the original payload, deduped by `tool_use_id` per model_family; format: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}` | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_response | `src/logs/dual_log/api_requests_<log_id>_response.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/parser.py:find_response_log_path` + `read_response_log` → `panes/token_pane.py` via `request_id` join; renders rate-limit (5h/7d utilization + reset) in the expanded token-pane call block | Response HTTP headers of the rate-limit family + request-id, joined by flow_id; filtered via `_filter_response_headers` (exact: `request-id`, `retry-after`, `anthropic-organization-id`; prefix: `anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`); written in the `responseheaders()` hook for ALL status codes (incl. 429 retry-after); format: `{flow_id, timestamp, request_id, status_code, headers: {…}}` | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_worker_dual_errors | `src/logs/dual_log/api_requests_worker_<hash>_<name>_<ts>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `scan_worker_errors_logs` (Stage 2D) | Worker-session derived tool-error log; same format as `_errors`; worker_name extracted from the filename | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| gpu_pane | `src/gpu_pane/logs/gpu_pane.log` | `gpu_pane/status.py:TimedRotatingFileHandler` | (no active reader) | GPU-monitoring status messages | Python log (`YYYY-MM-DD HH:MM:SS,mmm <level> msg`) | 7d timed rotation | live-handler |
| ccwrap_session | `src/ccwrap/logs/<stem>.bin + <stem>.ansi.log` | `ccwrap/ansi_log.py:open_log_pair` | (debug/analysis) | Raw ANSI terminal captures of CC sessions | Binary + ANSI-tab TSV | count-10-pairs | ccwrap-caller |
| polling_state | `src/logs/polling_state.jsonl` | `hooks/block_polling_loop.py:_record_and_count` | (no reader) | Polling-frequency state for the block_polling_loop hook (session×target counters, self-pruned to a 30s window) | JSONL (`ts` field) | 1d ts-records | monitor-24h |

### Two-Trigger Architecture

**Trigger 1 — proxy-start-bash** (`src/claude_proxy_start.sh:_janitor_cleanup_jsonl_logs` + `_janitor_version_purge_jsonl_logs` + `_compute_proxy_hash`):
- Responsible for `dual_log/` — per-class split: opus-originals keep-30 + worker-originals keep-30 separately; preceded by a version-aware purge (phase 0)
- Phase 0 (version purge, `_janitor_version_purge_jsonl_logs`): content hash (`_compute_proxy_hash`) over `proxy_addon.py` + `proxy/**/*.py` + `proxy/**/*.json` (sort-stable via `find … | sort`; excludes `*.pyc`, `*.md`, `.DS_Store`). Marker `dual_log/.proxy_version` (1 line = last hash). Hash change or missing marker → `find dual_log/ -maxdepth 1 -name "api_requests_*.jsonl" -mmin +60 -delete`; then the marker is written. Missing marker = first run = treated as a change (cleans up old logs on the first version-aware start). mtime < 60min = a live session = survives the purge.
- Phase 1a: `ls -t dual_log/api_requests_opus_*_original.jsonl | tail -n +31` → delete
- Phase 1b: `ls -t dual_log/api_requests_worker_*_original.jsonl | tail -n +31` → delete
- Phase 2: surviving `log_id`s = the union from the remaining `_original` files after rotation
- Phase 3: all other `dual_log/api_requests_*.jsonl` without a matching `log_id` deleted (suffix-stripping: original/forwarded/stripped/injected/errors/response — all suffixes of a log_id rotate together, suffix-aligned)
- Marker staleness: points at `dual_log/api_requests_<log_id>_forwarded.jsonl` (no longer the main log) — an mtime check verifies whether it's an active session; <60s → MARKER_IS_STALE=false
- Runs on every proxy start — independent of whether the Monitor is active
- Bash (not Python): count-based rotation via `ls -t | tail -n +31` is trivial in shell

**Trigger 2 — monitor-24h** (`src/core/monitor.py:run_main_loop`, 86400s guard):
- Responsible for the sweep-eligible JSONL logs (hook_firing, api_errors, polling_state)
- Python: `cleanup_old_jsonl(path)` from `src/log_janitor.py` via `sweep_eligible_specs(logs_dir)`
- Path resolution: `Path(__file__).parent.parent / 'logs'` from `src/core/monitor.py` = `src/logs/` — matches writer paths

**Not sweep-eligible (handler/caller-based):**
- `gpu_pane.log` → `TimedRotatingFileHandler` lives inside the gpu_pane process itself
- `*.bin + *.ansi.log` → `ccwrap/ansi_log.py:rotate_logs` is triggered by the ccwrap caller

### LogSpec Registry

`src/log_janitor.py` holds `_LOG_REGISTRY` (a tuple of 11 `LogSpec` entries, inventorying all logs). `sweep_eligible_specs(logs_dir)` returns `(spec, path)` pairs for the monitor-24h logs. `monitor.py` iterates over it — new sweep-eligible logs are automatically included by adding an entry to `_LOG_REGISTRY`.

`polling_state.jsonl` is primarily self-pruning (block_polling_loop prunes entries older than 30s on every call). The monitor-24h sweep via `cleanup_old_jsonl` is a backup in case the hook-side prune repeatedly fails (e.g. I/O errors). The effective retention in normal operation is 30 seconds.

### Message-Span Diffing (Strip/Inject)

`messages_delta` spans in `_stripped` and `_injected` entries are built via operation-transcript composition. Per-block logic in `_build_stripped_injected_deltas` (`logging.py`):

- `_all_ops` (`{msg_idx: {blk_idx: [(offset, removed, injected)]}}`) returned from `apply_modification_rules` as the 8th tuple element; stashed in `request()` as `flow.metadata["mc_all_ops"]`; read in `response()` and passed into `_build_stripped_injected_deltas(all_ops=...)`.
- Per block: `block_ops = msg_ops.get(bidx_int, [])` (empty default). `c0_text` extracted from the original content for all blocks via `_get_inner_text`. `spans = compose_block(c0_text, block_ops)` always — no `_diff_text` fallback for messages. Op-less (unmodified) blocks: `block_ops=[]` → `[("equal", c0_text)]` → `s_texts=[]`, `has_i=False` → nothing written. Output unchanged vs pre-Stage-4 for unmodified blocks: verified.
- `_diff_text` is not called for messages (Stage 4). `_diff_messages` produces block structure only (`{bidx, o_text, f_text}`, no `spans` field). `_diff_text` remains for system/tools (`_diff_system`, `_diff_tools`).
- Guard against mutation-without-op: `dev/proxy_dual_log/test_composition_invariant.py` — a committed synthetic fixture (9 entries, all 8 passes + dedup_wakeup + money-shot), exit 1 on any invariant violation. No runtime fallback.
- Double-inject fixed: a TN+BG chain produces 3 ops on msg[N] blk[0] (first_pass TN-strip+wakeup-inject, bg_exit BG-strip+wakeup-inject, dedup_wakeup removes the 2nd wakeup). `compose_block` yields exactly 1 injected wakeup span — offline-verified on the money-shot msg[100]: wakeup_count=1, has_i=True, badge fires. Live verification was pending a proxy restart at the time.
- Inner-content level: `_get_inner_text` returns `block["text"]` for text blocks, `block["content"]` for tool_result.

`compose_block`, `apply_edit_to_spans`, and `_get_inner_text` live in `src/proxy/diff_engine.py`.

## Evidence

- 108 `api_error_payload_*.json` files in `src/logs/`: 105/108 with `request_url` = `https://api.anthropic.com/v1/messages/count_tokens?beta=true` — evidence that `_is_messages_request` via `path.startswith("/v1/messages")` also caught count_tokens, and `_inject_model_override` injected `max_tokens` → API 400 `max_tokens: Extra inputs are not permitted`.
- The trigger decision (menubar-bundle problem), ts-format robustness, and module placement documented for the log janitor formed the basis for the two-trigger architecture.

**Main-log elimination feasibility probe (initial):**
- Script: `dev/proxy_dual_log/main_log_elimination_probe.py`
- Report: `dev/proxy_dual_log/main_log_elimination_probe_reports/20260604.md`
- Dataset: session `opus_monitor_cc_1780602018` at probe time (47 entries captured), positional match

| Check | Result |
|---|---|
| Content lossless (system/tools/messages) | 47/47 after cache_control-normalize (partial session — see full-session below) |
| Tool-error extraction vs tool_errors.jsonl | exact match (1 unique tool_use_id both sides) |
| BP:N counter derivable from quartet | no — pre-ops count not reconstructable — must be dropped |
| Missing top-level fields for proxy pane | `max_tokens` + `output_config` MUST-ADD to `_forwarded` |

**Full-session content-match verification (Stage 2B, readside2 worker):**
- Script: inline probe in the readside2 verification session (reuses `_reconstruct_forwarded` + `_normalize_elem` logic from the probe)
- Dataset: same session `opus_monitor_cc_1780602018`, all 118 entries at verification time (log grew as the session was live)

| Check | Result |
|---|---|
| Content lossless system | 118/118 after cache_control-normalize |
| Content lossless tools | 118/118 |
| Content lossless messages | 118/118 |
| Malformed/truncated forwarded lines | 0 — no JSONDecodeError, no partial writes |
| 113-vs-115 discrepancy (2B probe vs ground truth) | log was live; at 2B probe time the parser consumed to EOF (new_pos==file_size verified); ground truth of 115 measured later; now 118. No parser bug. |

## Recommendation (target state)

**Change: eliminate the main log (`api_requests_<id>.jsonl`), derive the monitor read-side from the dual-log quartet.**

Feasibility proven by the full-session probe (118/118 content lossless). Read-side migration complete (Stage 2 DONE). Remaining at the time: Stage 3 — write-side removal.

**Stage 2 — Read-side migration (DONE except 2E remaining):**
- **2A:** `BP:N` counter + latency badge removed from the proxy-pane header (`render_turn.py`, `format.py`)
- **2B:** `parser.py` forwarded-reconstruction core — `_parse_forwarded_log` (deque-bounded, `PROXY_MESSAGES_KEEP_LAST=10`), `_lazy_load_messages_forwarded`, `_summarize_fwd_message`/`_dict_to_list_fwd`/`_apply_delta_to_list`/`_extract_forwarded_fields` helpers; `find_errors_log_path`; `parse_proxy_log_forwarded`
- **2C:** `pane.py` + `worker_proxy_pane.py` wired to `parse_proxy_log_forwarded` / `_parse_forwarded_log`; state `_proxy_fwd_pos`/`_proxy_acc_fwd` replace `_proxy_pending_by_rid`; lazy-load uses `_lazy_load_messages_forwarded`
- **2D:** `warnings_pane` reads the `_errors` dual-log (main session via `find_errors_log_path` + `_read_errors_log`; workers via `scan_worker_errors_logs`); `warnings_scan`/`warnings_persist` stubbed; `warnings_parse` gutted
- **2E.1:** `diff_from_prev` restored in `_parse_forwarded_log` via `_compute_diff(prev_summaries, curr_summaries)` (20/20 offline match vs the main log); `_is_standalone_entry` rewritten to a content discriminator (`haiku OR sys_chars==0 AND tools_chars==0`), dropping `cache_breakpoints` guards
- **2E.2:** request numbering + sidecar gate fixed — `diff_from_prev.messages_added > 0` trigger replaces the dead `bp_len` / `entry_idx==0`; `opus_req_num` threads continuously (api_calls reseeding removed); `_is_standalone_entry` gate replaces the haiku-only check; haiku→`'H'`, non-haiku sidecar→`'S'`; retry (`messages_added==0`) → `#N.M`
- **2E.3:** SR/TN header badges (#4) — count badge re-sourced via a `flow_id` join on `_stripped`/`_injected` `fn_map`; `{n}strip` (YELLOW) / `{n}inj` (GREEN) on the REQ header; `_aggregate_entry_tags` removed
- **Badge false-positive fix** — four phantom `fn_map` sources eliminated; verified on real logs. **`fn_map` attribution rules:** (1) field overrides (`field.*` loc_keys — model, max_tokens, thinking, output_config, context_management) NOT written to `fn_map` at write-side in `_build_stripped_injected_deltas`; they appear only in `fields_delta`; (2) message, system, and tools-desc blocks whose only injected text is `"."` (empty-block placeholder — `strip_sr.py` `or '.'`, `_strip_sys3()` unconditional `"."`, `_apply_system_passes()` empty-rules `"."`) NOT written to `fn_map`; overlay dicts (`i_sys`/`i_tools`/`i_blks`) remain set; (3) `strip_sr.py` partial mode preserves the original trailing `\n` — no longer forwards a net-new `\n` when the original SR had none. Read-side `accumulate_dual_log` uses `set(fn_map.values())` (no `field.*` filter needed).
- **2E remaining at the time:** (c) a full live-verify on new-format logs needed a proxy restart

**Stage 3 — Write-side removal (DONE):**
- `api_requests_<id>.jsonl` write path removed: `_build_entry` / `_build_latency_update` / `_count_system_chars` / `_summarize_content_for_log` deleted from `proxy/logging.py`; main-log `_write_entry` calls + latency hook removed from `proxy/addon.py`
- `proxy/hash_meta.py` deleted (sent_meta writer + drift-report helpers — no callers)
- `proxy/schema_check.py` deleted (schema-warning writer — no callers after Block A)
- `tool_errors` + `api_requests_opus` + `api_requests_worker` LogSpec entries removed from `src/log_janitor.py:_LOG_REGISTRY`
- `warnings_persist.py` deleted; `warnings_scan.py` deleted
- 0:main strip overlay removed (`_refresh_strip_cache`, `ingest_proxy_strip_data`, `_strip_by_tool_id`, `_strip_prompt_ts_set`, `build_tool_id_strip_lookup`)
- 9 dead parser fns deleted (`_enrich_content_tails`, `_lazy_load_messages`, `_extract_raw_payload_fields`, `_parse_log_file`, `parse_proxy_log`, `scan_worker_logs`, `_subprocess_worker`, `_parse_log_file_isolated`, `parse_proxy_log_isolated`)
- Rotation re-anchored to `_original` files (per-class opus-30 + worker-30 split); marker staleness → `_forwarded.jsonl`; a pre-existing `_errors` suffix bug fixed
- `find_worker_proxy_log` updated: dual-log forwarded discovery as primary (globs `dual_log/api_requests_worker_*_forwarded.jsonl`), legacy main-log as fallback
