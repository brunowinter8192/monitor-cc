# src/proxy_display/

## Role

Proxy pane TUI package. Reads mitmproxy log entries from `src/logs/api_requests_*.jsonl`,
groups them by session turn, and renders an interactive expand/collapse display showing API
request structure (model, message counts, cache breakpoints, system/tools/messages detail).
Runs two event loops — one for the main session proxy log, one for the selected worker's proxy
log. Also exports `parse_proxy_log` and path helpers used by `metadata`, `panes.waste_pane`,
and `panes.warnings_pane`. Touch this package when changing proxy pane display logic or the
parser field extraction. Do NOT touch for the proxy modification pipeline — that lives in `src/proxy/`.

## Public Interface

- `run_proxy_loop` — main proxy pane event loop (entry point from `core.monitor`)
- `run_worker_proxy_loop` — worker proxy pane event loop (entry point from `core.monitor`)
- `parse_proxy_log(project_filter_or_path, last_position)` — parse proxy JSONL incrementally
- `find_worker_proxy_log(worker_name, project_filter=None)` — resolve proxy log path for a named worker; tries prefixed glob `api_requests_worker_{hash}_{name}_*.jsonl` first (when `project_filter` provided), falls back to unprefixed for older logs
- `_parse_log_file(path, last_position)` — low-level log file reader
- `format_proxy_block(entries, ...)` — render full proxy pane ANSI string

## Flow

`src/logs/api_requests_*.jsonl` → `parser` (incremental JSONL read via `readline()`, stamps `_byte_offset` per entry, raw_payload extraction → flat entry dicts, `del raw_payload`)
→ `pane` strip-on-extend: messages deleted from entries outside keep-last=10 window + not-expanded
→ `format` (group by turn — turns always expanded, viewport, scroll) → `render_turn` (req rows)
→ `render_sections` + `render_messages` (expanded req detail; requires messages — lazy-reload ensures they are present)
→ `pane` / `worker_proxy_pane` (event loop, stdin → stdout)

On expand-click: `_lazy_load_messages(entry, log_path)` seeks to `entry['_byte_offset']`, reads one JSONL line, re-populates `entry['messages']` + `content_tail` enrichment. Also reloads `prev_same` (first non-standalone predecessor) in the same click handler.

**Expand model (flat):** Turn boundaries are indicated by empty-line separators only (no header rows). Only Req-level and below are expandable. line_map contains only Req-level and deeper keys — one sequential phys_row counter through the visible slice, no nested offsets.

## Modules

### pane.py (252 LOC)

**Purpose:** Event loop for the main proxy pane — reads proxy log incrementally, handles mouse/keyboard input (click expand/collapse, scroll, hover), renders on change. Strip-on-extend: after each `proxy_entries.extend()`, strips `messages` from entries outside the `PROXY_MESSAGES_KEEP_LAST=10` window that are not actively expanded. On expand-click, lazy-reloads messages for the target entry AND its `prev_same` (first non-standalone predecessor) via `_lazy_load_messages`. Copy-button click on REQ header (col ≥ pane_width-2, row in `_proxy_copy_rows`) copies REQ content to clipboard via `_serialize_proxy`; ✓-flash for 1.5s after click via `_copy_feedback_until`. hover+y removed (copy-button is the sole copy mechanism). Module state: `_proxy_pane_width` (updated each render, used by click handler), `_proxy_copy_rows` (phys_rows with ⎘, populated by `format_proxy_block`), `_copy_feedback_until` (entry_idx → expiry float).
**Reads:** Module-level state (entries, expand states, scroll offset, hover row, line map, `_proxy_log_path`); active project filter from shared monitor state; stdin.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_proxy_loop`)
**Calls out:** `input` (click_handler), `panes` (token_pane.build_cache_turns)

---

### worker_proxy_pane.py (332 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches active workers, reads the selected worker's proxy log, handles digit-key worker switching, mouse/keyboard input, renders with worker-switcher header. Header height is computed via `utils.visual_line_count` to handle multi-line wrap correctly: `body_hover`, `content_height`, and `line_map` shift all use `header_lines` instead of a hardcoded 1. Same strip-on-extend + lazy-reload pattern as `pane.py` — `_strip_inactive_wp_messages` runs after each extend; click-expand triggers `_lazy_load_messages` for entry + `prev_same`; `_worker_proxy_log_path` holds the current worker's JSONL path. Copy-button identical to pane.py with `_worker_proxy_*` prefix state; `_worker_proxy_copy_rows` is shifted by `header_lines` after each `format_proxy_block` call (same shift as `worker_proxy_line_map`). hover+y removed.
**Reads:** Module-level state (including `_worker_proxy_log_path`); live worker list from `workers.worker_tmux`; worker selection IPC file.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_worker_proxy_loop`)
**Calls out:** `input` (click_handler), `workers` (worker_tmux), `panes` (token_pane.build_cache_turns), `utils` (visual_line_count)

---

### format.py (237 LOC)

**Purpose:** `format_proxy_block` — groups proxy entries by turn (turns always expanded, no turn-level header row emitted), applies scroll/viewport windowing, delegates rendering to `render_turn`, returns `(ansi_string, total_lines)` for scroll math. Accepts optional `copy_feedback: dict` (entry_idx→expiry) and `copy_rows_out: set` — both forwarded to `render_turn_expanded` / `_render_entry_lines`; in the visible-slice loop, `copy_rows_out` is populated with phys_rows of REQ header lines that contain ⎘ or ✓ (detected via substring check on the raw line before background processing). Turn-groups are separated by a single empty line; all visible rows are REQ-level or deeper. Helpers: `_fmt_effort(s) → 'hig'/'med'/'lo'/'-'`; `_fmt_thinking_budget(n) → 'Nk'/'N'/'-'` — both used by `render_turn.py` for per-REQ header fields. Also exports `_is_standalone_entry(entry) -> bool` — shared predicate used by `render_turn` and `render_entry` backward walks to skip structurally-separate entries (haiku, zero-context, and mc=1 CC title/summary sidecars where `message_count==1 and cache_breakpoints==[]`). Sidecar detection is intentional: walking past them gives the right prev_same for ⚠T/⚠S and for the expand-block unchanged comparison. Owns the row-background priority chain applied in the final render loop: hover > `DIM_YELLOW_BG` > collision > zebra. Collision detection is a Record-during-Render pass: `rendered_opus_labels: list[(entry_idx, num_label)]` is passed into `render_turn_expanded` and `_render_entry_lines`, which append each opus REQ's generated `#N` label; after all rows are rendered, a `Counter` over the labels identifies duplicates and produces `collision_entry_idxs: set[int]`. Any REQ-header row whose `entry_idx` is in that set gets `COLLISION_BG` — the same-#N abort-cascade marker (see `decisions/OldThemes/background_task_abort_cascade.md`). Helper `_fmt_thinking_budget(n: Optional[int]) -> str` — None→`'-'`, n<1000→`str(n)`, n≥1000→`'Nk'`; used by REQ-header only (via `render_turn.py`).
**Reads:** Entries list, expand states, line map, hover row, pane dimensions, scroll offset, turns list.
**Writes:** Nothing — returns `(ansi_string, total_lines)` tuple.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/render_turn.py` (imports `_is_standalone_entry`), `src/proxy_display/render_entry.py` (imports `_is_standalone_entry`)
**Calls out:** `format` (token_format)

---

### parser.py (398 LOC)

**Purpose:** Read and parse proxy log JSONL files — extract rich fields from `raw_payload` (system blocks, tools, messages, schema warnings) into flat entry dicts, then discard raw payload to save memory. `_parse_log_file` reads STREAMING line-by-line via `readline()` loop (captures `line_start = f.tell()` before each read to stamp `entry['_byte_offset']`; uses `f.tell()` after loop for `new_position`). `_byte_offset` is the byte position of each entry's JSONL line — used by `_lazy_load_messages` to seek-and-reload a stripped entry's `messages` list on demand. `_enrich_content_tails(stored_msgs, raw_msgs)` populates `content_tail` on each stored message from the corresponding raw_payload message content — extracted as a reusable helper called by both `_extract_raw_payload_fields` (initial parse) and `_lazy_load_messages` (reload). `sent_meta` and `latency_update` records are merged into the pending entry by `request_id` via `pending_by_rid` dict. Flat fields: `thinking_budget_tokens` from `raw_payload.thinking.budget_tokens`; `effort_value` from `raw_payload.output_config.effort`. **Subprocess-parse pattern:** `_parse_log_file_isolated` and `parse_proxy_log_isolated` are drop-in wrappers for the corresponding public functions; when `last_position == 0` (Initial Parse) they spawn a child process via `multiprocessing.get_context('spawn')` to bound pymalloc page retention — the child allocates the 3 GB parse peak and discards it on exit; the parent receives only stripped scalar fields (~10–20 MB) via `multiprocessing.Queue`. `messages` are dropped pre-IPC in `_subprocess_worker`; lazy-reload via `_byte_offset` handles on-demand reload. `pending_by_rid` is reconciled post-IPC: only pending RIDs are transferred; the parent rebuilds the dict using its own entry object references. Falls back to in-parent parse on subprocess failure, timeout (default 60 s, overridable via `SUBPROCESS_PARSE_TIMEOUT` env), or IPC error. All 4 initial-parse call sites in `pane.py`, `worker_proxy_pane.py`, and `metadata_pane.py` use the `_isolated` variants.
**Reads:** Proxy log JSONL file by project filter or direct path (incremental by byte position).
**Writes:** Nothing — returns `(entry_list, new_position)`.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/panes/warnings_pane.py`, `src/metadata/metadata_pane.py`
**Calls out:** —

---

### render_entry.py (215 LOC)

**Purpose:** Render a single proxy request entry (collapsed or expanded) into display lines — shows model, message count, cache breakpoints, change warnings, delta breakdown, and flat per-message list when expanded. Used only in no-turns mode (when turns list is empty). Supports copy-button ⎘ (same pattern as `render_turn.py`): right-aligned at `pane_width-1` when `copy_feedback` is not None and there is room. Msg rows are non-clickable (key=None); msg-level expand was removed to keep line_map flat. Emits suspect-tag badge (⚠PO,SR,TN,ND in RED) on REQ-header when new/modified msgs contain any of the 4 tags, via `_aggregate_entry_tags` import from `render_messages`. When expanded, emits a second line with aggregated bucket signals (`INERT:X  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets`; collapsed header unchanged. Backward walk for `prev_entry` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip structurally-separate candidates — ensures a sidecar or zero-context entry between two real REQs does not become the reference. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker.
**Reads:** Entry dict, all entries (for prev-entry lookup), expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_entry_tags`, `_aggregate_req_buckets`)

---

### render_turn.py (160 LOC)

**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/tools/messages rendering to section modules. REQ-header format: `▶/▼ #N model Nmsg BP:N eff:X think:Nk CR:N CC:N [mods] [warns] [deltas] [tag badge] [TTFB:Xs gen:Ytok/s [N-stalls(max Xs)]]`. Copy ⎘-symbol right-aligned at `pane_width-1` in each REQ header when `copy_feedback` is not None and there is room (visible_len ≤ pane_width-1-sym_cells); flashes ✓ for 1.5s after click using `copy_feedback.get(entry_idx)` expiry. Visible width computed via `sum(_cell_width(ch))` to handle wide chars (⚠ = 2 cells, ✓ = 2 cells, ⎘ = 1 cell) consistently with `truncate_visible`. `eff:X` shown when entry has a non-None `effort_value` (uses flat field via `_fmt_effort`; 'high'→'hig', 'low'→'lo', 'medium'→'med'). `think:Nk` shown for non-haiku entries when `max_tokens > 0` (sources from the request output cap, formatted via `_fmt_thinking_budget`; never shown for haiku). Emits suspect-tag badge (⚠PO,SR,TN,ND in RED) on REQ-header row when new/modified msgs contain any of the 4 tracked tag literals, via `_aggregate_entry_tags` import from `render_messages`. Emits latency badge at end of REQ header if entry has `ttfb_ms` / `output_tokens_per_sec` / `n_stalls` fields (color-coded: TTFB green<2s yellow<10s red≥10s; gen-rate green≥25 yellow≥10 red<10 tok/s; stalls yellow 1-2, red ≥3) via `_format_latency` from `format.py`. When a REQ is expanded, emits a second line with aggregated bucket signals (`INERT:X  IDX:N  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets` (counter-delta semantics for INERT, mirrors strip_audit._classify_req); collapsed header unchanged. Backward walk for `prev_same` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip standalone candidates. Expanded-REQ downstream calls — `_aggregate_req_buckets`, `render_system_blocks`, `render_tools`, `render_messages` — all use `_section_ref = None if is_standalone else prev_same`, not the BP-anchor. This aligns the "unchanged" expand display with the ⚠T/⚠S header warning on the same reference. `prev_entry_for_delta` (BP-anchor) is preserved for the header char-delta string and the BP-anchor carry-forward, not for the expanded-block comparisons. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker.
**Reads:** Group dict, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys, opus_req_num, sub_req_num)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_entry_tags`, `_aggregate_req_buckets`)

---

### render_sections.py (177 LOC)

**Purpose:** Render the system blocks section and tools section for an expanded request entry — handles unchanged detection, per-block expand/collapse, change highlights, `[STRIPPED]` markers on sys[3] and tool headers when descriptions were proxy-stripped, and DIM_YELLOW_BG pre-strip originals on expand (top-level tool description + per-parameter descriptions). After the in-array tools loop, two supplementary subsections render with `DIM_YELLOW_BG`: tools dropped by `_strip_unused_tools` (one row per name in `entry.stripped_unused_tools_names` with `[STRIPPED]` marker) and CC's deferred tools (one row per name in `entry.deferred_tools_names` with `[DEFERRED]` marker). Both are non-clickable rows. Tool-level `is_stripped_tool = t_name in TOOL_BLOCKLIST` highlighting was removed in the same change — that branch never fired because `tools_defs` is post-strip.
**Reads:** Entry dict, previous entry, expand states, pane width, modifications list.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** —

---

### render_messages.py (228 LOC)

**Purpose:** Render new/modified/removed messages for an expanded request entry — handles added messages (full block content) and diffs (content_tail), prefers `stripped_msg_removed` over `stripped_msg_originals` for stripped-message display. Per-chunk `EFF:RULE` label (e.g. `EFF:NAG`, `EFF:CMD`) is emitted on its own line above each chunk, computed via `strip_vocab.attribute_chunk`; the IDX case (indexed in smi but no chunks) appends `IDX` inline on the `[STRIPPED]` header row. Also exports `_aggregate_entry_tags(entry)` (suspect-tag badge helper for render_turn + render_entry) — diff-aware: returns `[]` immediately for byte-identical re-fires (`first_diff_index < 0`), treats `first_diff_index = None` (no `diff_from_prev` key) as first REQ (all msgs new, `start = 0`), otherwise filters `stripped_msg_removed` to indices ≥ `first_diff_index` only. And `_aggregate_req_buckets(entry, prev_entry)` — a thin delegate to `strip_vocab.classify_req` that returns the per-REQ 5-bucket signals (INERT codes, IDX msgs, LEAK/SUS signal strings) for the expanded REQ second line; semantics (chunk-diff EFFECTIVE, counter-delta INERT, smi-diff IDX, tag-scan LEAK/SUS) live in `strip_vocab` (all already diff-aware for byte-identical re-fires). Content rendering highlights 4 suspect tag literals with `LIGHT_RED_BG` via `_SUSPECT_TAG_RE` substitution.
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

Both are reset when session changes (new proxy log file detected via `find_proxy_log_path`). On reset, the log path is cleared to `None`.

**Lazy-reload invariant:** every entry in the entries list that is outside the `PROXY_MESSAGES_KEEP_LAST=10` tail window and not in `expand_states` has `messages` deleted (stripped). Entries inside the window or with an active expand key (`('req', i)`, `i`, or `(i, 'neg_delta')`) always retain messages. On expand-click, `_lazy_load_messages(entry, log_path)` reloads from `entry['_byte_offset']` in the JSONL file; `prev_same` (first non-standalone predecessor) is reloaded in the same click handler.
