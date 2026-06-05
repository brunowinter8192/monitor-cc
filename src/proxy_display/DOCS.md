# src/proxy_display/

## Role

Proxy pane TUI package. Reads mitmproxy forwarded-delta entries from
`src/logs/dual_log/api_requests_*_forwarded.jsonl`, reconstructs per-request
system/tools/messages via delta accumulation, and renders an interactive expand/collapse
display showing API request structure (model, message counts, system/tools/messages detail).
Additionally reads `src/logs/dual_log/*_stripped.jsonl` / `*_injected.jsonl` to drive a
yellow (DIM_YELLOW_BG) / green (DIM_GREEN_BG) overlay showing what the proxy stripped and
injected per request. Runs two event loops — one for the main session proxy log, one for the
selected worker's proxy log (both carry the full dual-log overlay). Also exports
`parse_proxy_log_forwarded`, `find_errors_log_path`, `scan_worker_errors_logs`, and path
helpers used by `panes.warnings_pane`. Touch this package when changing proxy pane display
logic or the parser field extraction. Do NOT touch for the proxy modification pipeline —
that lives in `src/proxy/`.

## Public Interface

- `run_proxy_loop` — main proxy pane event loop (entry point from `core.monitor`)
- `run_worker_proxy_loop` — worker proxy pane event loop (entry point from `core.monitor`)
- `parse_proxy_log_forwarded(project_filter, last_pos, acc_by_family)` — parse `_forwarded` dual-log incrementally; returns `(entries, new_pos)`
- `find_worker_proxy_log(worker_name, project_filter=None)` — resolve proxy log path for a named worker; tries prefixed glob `api_requests_worker_{hash}_{name}_*.jsonl` first (when `project_filter` provided), falls back to unprefixed for older logs
- `find_errors_log_path(project_filter)` — resolve `_errors` dual-log path for current proxy session; used by `warnings_pane`
- `scan_worker_errors_logs(last_positions, project_session_id, min_mtime)` — glob + incremental read of worker `_errors` logs; used by `warnings_pane`
- `format_proxy_block(entries, ...)` — render full proxy pane ANSI string

## Flow

`src/logs/dual_log/api_requests_*_forwarded.jsonl` → `parser._parse_forwarded_log` (incremental JSONL read, delta accumulation per model family via `_apply_delta_to_list`/`_dict_to_list_fwd`, message summaries via `_summarize_fwd_message`, deque-bounded: last `PROXY_MESSAGES_KEEP_LAST=10` entries get `messages`, rest carry `messages=None`)
→ `pane` (entries extended; entries outside window + not-expanded carry `messages=None`)
→ `format` (group by turn — turns always expanded, viewport, scroll) → `render_turn` (req rows)
→ `render_sections` + `render_messages` (expanded req detail; requires messages — lazy-reload ensures they are present)
→ `pane` / `worker_proxy_pane` (event loop, stdin → stdout)

On expand-click: `_lazy_load_messages_forwarded(entry, fwd_path)` replays forwarded delta stream from byte 0 to `entry['_fwd_req_idx']`, reconstructs and populates `entry['messages']`. Also reloads `prev_same` in the same click handler.

**Expand model (flat):** Turn boundaries are indicated by empty-line separators only (no header rows). Only Req-level and below are expandable. line_map contains only Req-level and deeper keys — one sequential phys_row counter through the visible slice, no nested offsets.

## Modules

### pane.py (340 LOC)

**Purpose:** Event loop for the main proxy pane — reads `_forwarded` dual-log incrementally, handles mouse input (click expand/collapse, scroll, hover), renders on change. Drain-refresh-render pattern: `run_proxy_loop` is a ~47-LOC skeleton delegating to 4 helpers. Deque-bounded messages: only the last `PROXY_MESSAGES_KEEP_LAST=10` entries have `messages` populated by `_parse_forwarded_log`; entries outside that window carry `messages=None` and are lazy-loaded on expand-click. On expand-click, lazy-reloads messages for the target entry AND its `prev_same` (first non-standalone predecessor) via `_lazy_load_messages_forwarded(entry, fwd_path)` where `fwd_path = _proxy_log_path.parent / 'dual_log' / f'{_proxy_log_path.stem}_forwarded.jsonl'`. Copy-button click on REQ header copies REQ content to clipboard; ✓-flash for 1.5s after click. **Forwarded-log state:** `_proxy_fwd_pos` (int, byte position in `_forwarded` file, reset to 0 on session change/reparse); `_proxy_acc_fwd` (dict, family accumulator for `_parse_forwarded_log`, cleared on reset). **Dual-log overlay accumulator (unchanged from pre-migration):** `_proxy_stripped_pos` / `_proxy_injected_pos` + `_proxy_acc_stripped` / `_proxy_acc_injected` for `_stripped`/`_injected` overlay; entries hold references to family acc dict (`_stripped_spans` / `_injected_spans`) and to the per-family `_fns_by_flow_id` dict (`_strip_fns_lookup` / `_inject_fns_lookup`) — all four as Python references so late-arriving stripped/injected responses auto-propagate. Session-change + time-triggered reset blocks clear all fwd + overlay state vars.
**Reads:** Module-level state; active project filter from shared monitor state; stdin.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_proxy_loop`)
**Calls out:** `input` (click_handler), `panes` (token_pane.build_cache_turns), `proxy_display.parser` (`parse_proxy_log_forwarded`, `_lazy_load_messages_forwarded`, `find_proxy_log_path`, `_find_dual_log_paths`, `accumulate_dual_log`, `_infer_model_family`)

---

### worker_proxy_pane.py (426 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches active workers, reads the selected worker's `_forwarded` dual-log, handles digit-key worker switching, mouse input, renders with worker-switcher header. Drain-refresh-render pattern with `force_reload-OR-tick` gate. **Forwarded-log state:** `_worker_proxy_fwd_pos` (int) + `_worker_proxy_acc_fwd` (dict) replace `_worker_proxy_pending_by_rid`. In `_refresh_worker_proxy_data`: `fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'`; calls `_parse_forwarded_log(fwd_path, _worker_proxy_fwd_pos, _worker_proxy_acc_fwd)` directly; stamps `entry['_source_file'] = fwd_path.name` on each new entry. Lazy-load: same `_lazy_load_messages_forwarded` pattern, fwd_path derived from `_worker_proxy_log_path`. Worker-change + time-triggered reset blocks clear fwd state vars. **Dual-log overlay accumulator (unchanged):** `_worker_proxy_stripped_pos` / `_worker_proxy_injected_pos` + `_worker_proxy_acc_stripped` / `_worker_proxy_acc_injected` — both reset triggers clear all four. Entries receive `_strip_fns_lookup` / `_inject_fns_lookup` references to the per-family `_fns_by_flow_id` dicts (same pattern as main pane). `_worker_proxy_log_path` still updated to `log_path` (used for overlay path derivation and lazy-load fwd_path derivation). Header rendered via overdraw pattern; `_build_worker_proxy_output` returns `(output, header)` tuple.
**Reads:** Module-level state; live worker list from `workers.worker_tmux`; worker selection IPC file.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_worker_proxy_loop`)
**Calls out:** `input` (click_handler), `workers` (worker_tmux, worker_pane.get_selection_file_path, write_selection), `panes` (token_pane.build_cache_turns), `utils` (visual_line_count), `proxy_display.parser` (`find_worker_proxy_log`, `_parse_forwarded_log`, `_lazy_load_messages_forwarded`, `_find_dual_log_paths`, `accumulate_dual_log`, `_infer_model_family`)

---

### format.py (215 LOC)

**Purpose:** `format_proxy_block` — groups proxy entries by turn (turns always expanded, no turn-level header row emitted), applies scroll/viewport windowing, delegates rendering to `render_turn`, returns `(ansi_string, total_lines)` for scroll math. Accepts optional `copy_feedback: dict` (entry_idx→expiry) and `copy_rows_out: set` — both forwarded to `render_turn_expanded` / `_render_entry_lines`; in the visible-slice loop, `copy_rows_out` is populated with phys_rows of REQ header lines that contain ⎘ or ✓ (detected via substring check on the raw line before background processing). Turn-groups are separated by a single empty line; all visible rows are REQ-level or deeper. Helpers: `_fmt_effort(s) → 'hig'/'med'/'lo'/'-'`; `_fmt_thinking_budget(n) → 'Nk'/'N'/'-'` — both used by `render_turn.py` for per-REQ header fields. Also exports `_is_standalone_entry(entry) -> bool` — shared predicate used by `render_turn` and `render_entry` backward walks to skip structurally-separate entries (haiku or zero-context). Content discriminator: `haiku OR (sys_chars==0 AND tools_chars==0)`. Real main-session requests always carry the full CC system prompt and tool list (`sys_chars>0`, `tools_chars>0`); CC title/summary and haiku sidecars have neither. Old `cache_breakpoints`-guarded branches and the `mc==1` branch are gone — `cache_breakpoints` is always `[]` for forwarded entries, those guards were meaningless. Backward-compatible with main-log entries (real first-REQs had bp=[0] AND sys_chars>0; same sys_chars>0 guard protects them). Sidecar detection is intentional: walking past them gives the right prev_same for ⚠T/⚠S and for the expand-block unchanged comparison. **Request numbering:** `#N` (fresh) when `(entry.get('diff_from_prev') or {}).get('messages_added', 1) > 0`; retry/abort re-send (`messages_added==0`) → `#N.M`. Sidecars excluded via `_is_standalone_entry`: haiku → `'H'`, non-haiku sidecar (sys=0, tools=0) → `'S'`; neither increments the counter. `opus_req_num` threads continuously via `render_turn_expanded`'s return value — NOT reseeded from `api_calls` per turn-group. Owns the row-background priority chain applied in the final render loop: hover > `DIM_YELLOW_BG` > collision > zebra. Collision detection is a Record-during-Render pass: `rendered_opus_labels: list[(entry_idx, num_label)]` is passed into `render_turn_expanded` and `_render_entry_lines`, which append each non-standalone REQ's generated label; after all rows are rendered, a `Counter` over the labels identifies duplicates and produces `collision_entry_idxs: set[int]`. Any REQ-header row whose `entry_idx` is in that set gets `COLLISION_BG` — the same-#N abort-cascade marker (see `decisions/OldThemes/abort_cascade/background_task_abort_cascade.md`). Helper `_fmt_thinking_budget(n: Optional[int]) -> str` — None→`'-'`, n<1000→`str(n)`, n≥1000→`'Nk'`; used by REQ-header only (via `render_turn.py`).
**Reads:** Entries list, expand states, line map, hover row, pane dimensions, scroll offset, turns list.
**Writes:** Nothing — returns `(ansi_string, total_lines)` tuple.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/render_turn.py` (imports `_is_standalone_entry`), `src/proxy_display/render_entry.py` (imports `_is_standalone_entry`)
**Calls out:** `format` (token_format)

---

### parser.py (798 LOC)

**Purpose:** Parse proxy dual-log files and reconstruct per-request entries for the proxy pane. **Active path — forwarded reconstruction:** `parse_proxy_log_forwarded(project_filter, last_pos, acc_by_family)` resolves the `_forwarded` dual-log via marker file and delegates to `_parse_forwarded_log`. `_parse_forwarded_log(fwd_path, last_pos, acc_by_family)` reads `forwarded_delta` JSONL lines incrementally, accumulates system/tools/message deltas per model family via `_apply_delta_to_list` / `_dict_to_list_fwd`, summarises messages via `_summarize_fwd_message`, builds entry dicts via `_extract_forwarded_fields` (stamps `entry['_fwd_req_idx']` as 0-based position in the forwarded stream; sets `entry['cache_breakpoints'] = []` always), stamps `entry['flow_id']` from the raw JSONL line (mitmproxy UUID4 per-flow, join key for per-request fn_map lookup), stamps `entry['diff_from_prev'] = _compute_diff(prev_summaries, new_summaries)` (captures prev summaries from accumulator before update; `None` for `is_first=True` entries), and applies deque bound: only the last `PROXY_MESSAGES_KEEP_LAST=10` entries have `entry['messages']` populated; earlier entries carry `messages=None`. `_lazy_load_messages_forwarded(entry, fwd_path)` replays the forwarded stream from byte 0 to `entry['_fwd_req_idx']`, reconstructing messages for a stripped entry on expand-click. `find_errors_log_path(project_filter)` resolves the `_errors` dual-log path for the current proxy session (used by `warnings_pane`). `scan_worker_errors_logs(last_positions, project_session_id, min_mtime)` globs worker `_errors` dual-logs under `logs/dual_log/`, reads incrementally by byte position, extracts `_worker_name_from_file` from filename. **Dual-log overlay helpers (active):** `_find_dual_log_paths`, `_infer_model_family`, `accumulate_dual_log` — used by `pane.py` / `worker_proxy_pane.py` for stripped/injected overlay; `accumulate_dual_log` mutates `acc_by_family` IN-PLACE (`.clear()`+`.update()` preserves Python refs held by pane entries); additionally maintains `acc['_fns_by_flow_id']: {flow_id → set(fn_names)}` per family — appends `set(fn_map.values())` keyed by `flow_id` for each new line, cleared in-place on `is_first`; `_stripped` and `_injected` accumulators each carry their own `_fns_by_flow_id`. **Old main-log path (still present, no longer called by panes):** `_parse_log_file` (line-by-line JSONL reader stamping `entry['_byte_offset']`), `_lazy_load_messages` (seek-and-reload via `_byte_offset`), `_enrich_content_tails`, `_extract_raw_payload_fields`, `_parse_log_file_isolated` / `_subprocess_worker` (subprocess offload pattern), `parse_proxy_log_isolated`, `parse_proxy_log`, `scan_worker_logs` — with `sent_meta` / `latency_update` merge via `pending_by_rid`; none of these are called by `pane.py` or `worker_proxy_pane.py` after Stage 2.
**Reads:** `_forwarded` / `_errors` dual-log JSONL files by project filter (incremental by byte position). `_stripped` / `_injected` dual-log files via `accumulate_dual_log`.
**Writes:** Nothing — returns `(entry_list, new_position)` tuples.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py` (`parse_proxy_log_forwarded`, `_parse_forwarded_log`, `_lazy_load_messages_forwarded`, `_find_dual_log_paths`, `accumulate_dual_log`, `_infer_model_family`); `src/panes/warnings_pane.py` (`find_errors_log_path`, `scan_worker_errors_logs`, `proxy_session_id_for_project`, `get_proxy_session_start_ts`)
**Calls out:** `proxy.message_summary` (`_summarize_message`)

---

### render_entry.py (221 LOC)

**Purpose:** Render a single proxy request entry (collapsed or expanded) into display lines — shows model, message count, change warnings, delta breakdown, and flat per-message list when expanded. Used only in no-turns mode (when turns list is empty). Supports copy-button ⎘ (same pattern as `render_turn.py`): right-aligned at `pane_width-1` when `copy_feedback` is not None and there is room. Msg rows are non-clickable (key=None); msg-level expand was removed to keep line_map flat. Emits count badge on REQ-header: `{n}strip` (YELLOW) and/or `{n}inj` (GREEN), where n = number of distinct strip/inject functions that fired this request, resolved via `entry['_strip_fns_lookup'].get(entry['flow_id'], set())`; only non-zero parts shown; both zero → no badge. When expanded, emits a second line with aggregated bucket signals (`INERT:X  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets`; collapsed header unchanged. Backward walk for `prev_entry` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip structurally-separate candidates — ensures a sidecar or zero-context entry between two real REQs does not become the reference. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker. In expanded view: calls `render_fields_delta(entry_idx, entry, expand_states, pane_width)` immediately after the horizontal divider — no-ops when `_stripped_spans` absent or fields dicts empty.
**Reads:** Entry dict, all entries (for prev-entry lookup), expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_req_buckets`), `render_sections` (`render_fields_delta`)

---

### render_turn.py (159 LOC)

**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/tools/messages rendering to section modules. REQ-header format: `▶/▼ #N model Nmsg [eff:X] [think:Nk] CR:N CC:N [mods] [warns] [deltas] [tag badge]`. **Numbering:** `_is_standalone_entry` gate: haiku → `'H'`, non-haiku sidecar (sys=0, tools=0) → `'S'`; for real requests: `#N` when `(entry.get('diff_from_prev') or {}).get('messages_added', 1) > 0` (fresh message list added), `#N.M` when `messages_added==0` (retry/abort re-send of same list). Copy ⎘-symbol right-aligned at `pane_width-1` in each REQ header when `copy_feedback` is not None and there is room (visible_len ≤ pane_width-1-sym_cells); flashes ✓ for 1.5s after click using `copy_feedback.get(entry_idx)` expiry. Visible width computed via `sum(_cell_width(ch))` to handle wide chars (⚠ = 2 cells, ✓ = 2 cells, ⎘ = 1 cell) consistently with `truncate_visible`. `eff:X` shown when entry has a non-None `effort_value` (uses flat field via `_fmt_effort`; 'high'→'hig', 'low'→'lo', 'medium'→'med'). `think:Nk` shown for non-haiku entries when `max_tokens > 0` (sources from the request output cap, formatted via `_fmt_thinking_budget`; never shown for haiku). Emits count badge on REQ-header: `{n}strip` (YELLOW) and/or `{n}inj` (GREEN), where n = number of distinct strip/inject functions that fired this request, resolved via `entry['_strip_fns_lookup'].get(entry['flow_id'], set())`; only non-zero parts shown; both zero → no badge. When a REQ is expanded, emits a second line with aggregated bucket signals (`INERT:X  IDX:N  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets` (counter-delta semantics for INERT, mirrors strip_audit._classify_req); collapsed header unchanged. Backward walk for `prev_same` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip standalone candidates. Expanded-REQ downstream calls — `_aggregate_req_buckets`, `render_fields_delta`, `render_system_blocks`, `render_tools`, `render_messages` — all use `_section_ref = None if is_standalone else prev_same`, not the BP-anchor. Order: `render_fields_delta` (payload-level field changes) is called FIRST, above `render_system_blocks` — no-ops when `_stripped_spans` absent or fields dicts empty. This aligns the "unchanged" expand display with the ⚠T/⚠S header warning on the same reference. `prev_entry_for_delta` (BP-anchor) is preserved for the header char-delta string and the BP-anchor carry-forward, not for the expanded-block comparisons. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker.
**Reads:** Group dict, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys, opus_req_num, sub_req_num)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_req_buckets`), `render_sections` (`render_system_blocks`, `render_tools`, `render_fields_delta`)

---

### render_sections.py (301 LOC)

**Purpose:** Render system blocks, tools, and fields-delta sections for an expanded request entry. All three functions share the same dual-color sentinel: `use_dual = '_stripped_spans' in entry` / `if '_stripped_spans' in entry:`. New path uses `entry['_stripped_spans']` / `entry['_injected_spans']` span data from the dual-log accumulator; `else:` path keeps the old side-channel unchanged (worker pane has no `_stripped_spans`).

`render_system_blocks`: per-block delta visibility — unchanged detection is content-based (`sb.get('preview','') == prev.get('preview','')`) per block; first request shows all blocks; subsequent requests skip unchanged blocks entirely (no `(unchanged)` placeholder). Block header coloring: DIM_YELLOW_BG when `s_spans` present, DIM_GREEN_BG when `i_spans` present, gray otherwise. No text labels. On expand (use_dual path): if `i_spans` is new-format (`isinstance(i_spans[0], (list, tuple))`), renders inline — equal=DIM gray, injected=DIM_GREEN_BG green; then `s_spans` (flat strings) DIM_YELLOW_BG stacked below. Old-format or no i_spans: gray preview + stacked yellow/green (legacy path, backward-compat). Old path (no dual): hardcoded sys[2]/sys[3] detection via `mods`, yellow `original_text`.

`render_tools`: tool NAME line is gray for all forwarded and desc-only-changed tools; DIM_GREEN_BG only for whole-injected tools (`i_tool.get('whole')`). No text labels on name lines. Unchanged tools section: when tools hash unchanged (non-first request), the entire section is omitted — `render_tools` returns `([], [])` immediately before the header append; header, whole-stripped rows, and deferred rows are all absent. Desc-changes path: if `i_desc` is new-format, inline render (equal=DIM, injected=DIM_GREEN_BG); `s_desc` stacked yellow below. Old-format i_desc: forwarded description + stacked yellow/green (legacy path). Whole-stripped extra rows: DIM_YELLOW_BG `▶ name` (no label text), `keys.append(None)` (non-expandable). Old path: `stripped_original`, `stripped_unused_tools_names`.

`render_fields_delta`: collapsible `('fields', entry_idx)` header; when expanded, one line per key — yellow DIM_YELLOW_BG old value, green DIM_GREEN_BG new value, pair for replaced. No-ops when `_stripped_spans` absent or both fields dicts empty.
**Reads:** Entry dict, previous entry, expand states, pane width, modifications list.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`, `src/proxy_display/render_entry.py`
**Calls out:** —

---

### render_messages.py (309 LOC)

**Purpose:** Render new/modified/removed messages for an expanded request entry — handles added messages (full block content) and diffs (content_tail). Dual-color sentinel: `use_dual = '_stripped_spans' in entry`. Per block: resolves `i_blk` from `entry['_injected_spans']['messages'][midx][bidx]` and `s_blk` from `_stripped_spans`. If `i_blk` is new-format (`isinstance(i_blk[0], (list, tuple))`): inline render — iterates `[(tag, text), ...]`, equal=DIM gray (with suspect-tag highlight), injected=DIM_GREEN_BG green; `s_blk` (flat strings) stacked DIM_YELLOW_BG below; gray `full_text` block suppressed. Old-format or no i_blk: gray `full_text` as before, then stacked s_blk yellow + i_blk green (legacy path, backward-compat). Both branches of the outer msg-count conditional (`prev_msg_count < len(messages)` vs `else`) carry identical inline-vs-legacy dispatch. `_render_stripped_block` calls (old side-channel) guarded with `and not use_dual`. EFF:RULE attribution kept in old path only. Also exports `_aggregate_req_buckets(entry, prev_entry)` (5-bucket classify_req delegate). `_SUSPECT_TAG_RE` highlights 4 suspect tags with `LIGHT_RED_BG` — applied to equal spans as well in new render path.
**Reads:** Entry dict, previous entry, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** `proxy.strip_vocab` (`attribute_chunk`, `classify_tags`, `code_for_rule`, `classify_req`)

---

## State

`pane.py` and `worker_proxy_pane.py` each own independent module-level mutable state:
- entries list, expand states dict, scroll offset, hover row, line map, turns list
- `_proxy_log_path` / `_worker_proxy_log_path` — current JSONL path, updated each poll cycle; used by lazy-reload on expand-click and clipboard copy
- `_proxy_pane_width` / `_worker_proxy_pane_width` — last rendered pane width (default 80); used by copy-button click handler to determine column threshold
- `_proxy_copy_rows` / `_worker_proxy_copy_rows` — set of phys_rows where ⎘ was rendered; cleared before each `format_proxy_block` call and repopulated; `_worker_proxy_copy_rows` is shifted by `header_lines` after each call
- `_copy_feedback_until` / `_worker_copy_feedback_until` — entry_idx→float dicts for ✓ flash; cleaned up each poll cycle; non-empty dict keeps `input_changed=True` for animation refresh

**Dual-log accumulator (both panes):**
- `_proxy_stripped_pos` / `_proxy_injected_pos` (`pane.py`) and `_worker_proxy_stripped_pos` / `_worker_proxy_injected_pos` (`worker_proxy_pane.py`) — byte-position cursors for incremental dual-log reads; reset to 0 on session/worker change
- `_proxy_acc_stripped` / `_proxy_acc_injected` (`pane.py`) and `_worker_proxy_acc_stripped` / `_worker_proxy_acc_injected` (`worker_proxy_pane.py`) — `{family: {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}}` accumulator dicts; mutated IN-PLACE by `accumulate_dual_log` (`.clear()`+`.update()` on section dicts preserves Python references); cleared on reset via `.clear()`. Each newly-parsed entry holds a REFERENCE to its family's accumulator dict — NOT a copy. Render code reads span data from these references at render time, so late-arriving delta updates propagate automatically. Worker pane has two reset triggers (worker-change detection + time-triggered reparse); both clear all four dual-log vars.

Both are reset when session/worker changes. On reset, the log path is cleared to `None`.

**Lazy-reload invariant:** every entry in the entries list that is outside the `PROXY_MESSAGES_KEEP_LAST=10` tail window and not in `expand_states` has `messages=None` (stripped by `_parse_forwarded_log`). Entries inside the deque window or with an active expand key (`('req', i)`, `i`, or `(i, 'neg_delta')`) always retain messages. On expand-click, `_lazy_load_messages_forwarded(entry, fwd_path)` replays the forwarded delta stream from byte 0 to `entry['_fwd_req_idx']` to reconstruct messages; `prev_same` (first non-standalone predecessor) is reloaded in the same click handler.
