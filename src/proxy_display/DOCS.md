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

`src/logs/api_requests_*.jsonl` → `parser` (incremental JSONL read, raw_payload extraction → flat entry dicts)
→ `format` (group by turn — turns always expanded, viewport, scroll) → `render_turn` (req rows)
→ `render_sections` + `render_messages` (expanded req detail)
→ `pane` / `worker_proxy_pane` (event loop, stdin → stdout)

**Expand model (flat):** Turns are static info-headers (non-clickable, always visible). Only Req-level and below are expandable. line_map contains only Req-level and deeper keys — one sequential phys_row counter through the visible slice, no nested offsets.

## Modules

### pane.py (176 LOC)

**Purpose:** Event loop for the main proxy pane — reads proxy log incrementally, handles mouse/keyboard input (click expand/collapse, scroll, hover), renders on change.
**Reads:** Module-level state (entries, expand states, scroll offset, hover row, line map); active project filter from shared monitor state; stdin.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_proxy_loop`)
**Calls out:** `input` (click_handler), `panes` (token_pane.build_cache_turns)

---

### worker_proxy_pane.py (249 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches active workers, reads the selected worker's proxy log, handles digit-key worker switching, mouse/keyboard input, renders with worker-switcher header. Header height is computed via `utils.visual_line_count` to handle multi-line wrap correctly: `body_hover`, `content_height`, and `line_map` shift all use `header_lines` instead of a hardcoded 1.
**Reads:** Module-level state; live worker list from `workers.worker_tmux`; worker selection IPC file.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_worker_proxy_loop`)
**Calls out:** `input` (click_handler), `workers` (worker_tmux), `panes` (token_pane.build_cache_turns), `utils` (visual_line_count)

---

### format.py (242 LOC)

**Purpose:** `format_proxy_block` — groups proxy entries by turn (turns always expanded, turn header key=None), applies scroll/viewport windowing, delegates rendering to `render_turn`, returns `(ansi_string, total_lines)` for scroll math. Turn-header format: `Turn N [HH:MM]  effort:Xk  think:Nk  Δmsgs:±...` — effort is the highest-priority value across all opus entries in the turn (high>medium>low, via `_fmt_effort`); budget is max non-None `thinking_budget_tokens`; Δsys and Δtools intentionally omitted to reduce noise. Helpers: `_fmt_effort(s) → 'hig'/'med'/'lo'/'-'`; `_fmt_thinking_budget(n) → 'Nk'/'N'/'-'`. Also exports `_is_standalone_entry(entry) -> bool` — shared predicate used by `render_turn` and `render_entry` backward walks to skip structurally-separate entries (haiku, zero-context, and mc=1 CC title/summary sidecars where `message_count==1 and cache_breakpoints==[]`). Sidecar detection is intentional: walking past them gives the right prev_same for ⚠T/⚠S and for the expand-block unchanged comparison. Owns the row-background priority chain applied in the final render loop: hover > `DIM_YELLOW_BG` > collision > zebra. Collision detection is a Record-during-Render pass: `rendered_opus_labels: list[(entry_idx, num_label)]` is passed into `render_turn_expanded` and `_render_entry_lines`, which append each opus REQ's generated `#N` label; after all rows are rendered, a `Counter` over the labels identifies duplicates and produces `collision_entry_idxs: set[int]`. Any REQ-header row whose `entry_idx` is in that set gets `COLLISION_BG` — the same-#N abort-cascade marker (see `decisions/OldThemes/background_task_abort_cascade.md`). Helper `_fmt_thinking_budget(n: Optional[int]) -> str` — None→`'-'`, n<1000→`str(n)`, n≥1000→`'Nk'`; used by both Turn-header and REQ-header.
**Reads:** Entries list, expand states, line map, hover row, pane dimensions, scroll offset, turns list.
**Writes:** Nothing — returns `(ansi_string, total_lines)` tuple.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/render_turn.py` (imports `_is_standalone_entry`), `src/proxy_display/render_entry.py` (imports `_is_standalone_entry`)
**Calls out:** `format` (token_format)

---

### parser.py (243 LOC)

**Purpose:** Read and parse proxy log JSONL files — extract rich fields from `raw_payload` (system blocks, tools, messages, schema warnings) into flat entry dicts, then discard raw payload to save memory. `_parse_log_file` reads STREAMING line-by-line via `for line in f` (no `f.read()` peak) and uses `f.tell()` after the loop for the new position (avoids TOCTOU race with proxy writer adding lines mid-read). The `sent_meta` lookback (merge `sent_*` fields into the previous entry) is implemented via a `last_entry` local variable instead of `entries[-1]`. `latency_update` records (type=latency_update) are handled the same way: matched to `last_entry` by `request_id`, fields `ttfb_ms`, `stream_duration_ms`, `output_tokens_per_sec`, `n_stalls`, `max_stall_ms`, `total_stall_ms` are merged in. Flat fields: `thinking_budget_tokens` from `raw_payload.thinking.budget_tokens` (None if absent); `effort_value` from `raw_payload.output_config.effort` (None if absent — set by proxy `injected_model_override` + `capped_post_sleep` rules). **Known open issue:** despite streaming, peak RAM is still O(N²) because each proxy entry's `raw_payload.messages` is the full cumulative conversation; building all parsed entries in memory still hits gigabytes for long sessions. Real fix needs per-entry process-and-drop or message-strip-on-parse — see Bead Monitor_CC-lhf and `sources/RAM_research_2026-04-25.md`.
**Reads:** Proxy log JSONL file by project filter or direct path (incremental by byte position).
**Writes:** Nothing — returns `(entry_list, new_position)`.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/panes/waste_pane.py`, `src/panes/warnings_pane.py`, `src/metadata/metadata_pane.py`
**Calls out:** —

---

### render_entry.py (200 LOC)

**Purpose:** Render a single proxy request entry (collapsed or expanded) into display lines — shows model, message count, cache breakpoints, change warnings, delta breakdown, and flat per-message list when expanded. Used only in no-turns mode (when turns list is empty). Msg rows are non-clickable (key=None); msg-level expand was removed to keep line_map flat. Emits suspect-tag badge (⚠PO,SR,TN,ND in RED) on REQ-header when new/modified msgs contain any of the 4 tags, via `_aggregate_entry_tags` import from `render_messages`. When expanded, emits a second line with aggregated bucket signals (`INERT:X  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets`; collapsed header unchanged. Backward walk for `prev_entry` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip structurally-separate candidates — ensures a sidecar or zero-context entry between two real REQs does not become the reference. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker.
**Reads:** Entry dict, all entries (for prev-entry lookup), expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_entry_tags`, `_aggregate_req_buckets`)

---

### render_turn.py (141 LOC)

**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/tools/messages rendering to section modules. REQ-header format: `▶/▼ #N model Nmsg BP:N eff:X think:Nk CR:N CC:N [mods] [warns] [deltas] [tag badge] [TTFB:Xs gen:Ytok/s [N-stalls(max Xs)]]`. `eff:X` shown when entry has a non-None `effort_value` (uses flat field via `_fmt_effort`; 'high'→'hig', 'low'→'lo', 'medium'→'med'). `think:Nk` shown when entry has a non-empty `thinking_config` (uses flat `thinking_budget_tokens` via `_fmt_thinking_budget`; shows `think:-` for adaptive with no budget). Emits suspect-tag badge (⚠PO,SR,TN,ND in RED) on REQ-header row when new/modified msgs contain any of the 4 tracked tag literals, via `_aggregate_entry_tags` import from `render_messages`. Emits latency badge at end of REQ header if entry has `ttfb_ms` / `output_tokens_per_sec` / `n_stalls` fields (color-coded: TTFB green<2s yellow<10s red≥10s; gen-rate green≥25 yellow≥10 red<10 tok/s; stalls yellow 1-2, red ≥3) via `_format_latency` from `format.py`. When a REQ is expanded, emits a second line with aggregated bucket signals (`INERT:X  IDX:N  LEAK:<TN>  SUS:<PO>`) computed via `_aggregate_req_buckets` (counter-delta semantics for INERT, mirrors strip_audit._classify_req); collapsed header unchanged. Backward walk for `prev_same` (reference for ⚠T/⚠S) uses `format._is_standalone_entry` to skip standalone candidates. Expanded-REQ downstream calls — `_aggregate_req_buckets`, `render_system_blocks`, `render_tools`, `render_messages` — all use `_section_ref = None if is_standalone else prev_same`, not the BP-anchor. This aligns the "unchanged" expand display with the ⚠T/⚠S header warning on the same reference. `prev_entry_for_delta` (BP-anchor) is preserved for the header char-delta string and the BP-anchor carry-forward, not for the expanded-block comparisons. Accepts optional `rendered_opus_labels: list` param; when non-None, appends `(entry_idx, num_label)` per non-haiku non-standalone opus REQ so `format.py` can post-process the list into `collision_entry_idxs` for the COLLISION_BG marker.
**Reads:** Group dict, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys, opus_req_num, sub_req_num)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** `render_messages` (`_aggregate_entry_tags`, `_aggregate_req_buckets`)

---

### render_sections.py (172 LOC)

**Purpose:** Render the system blocks section and tools section for an expanded request entry — handles unchanged detection, per-block expand/collapse, change highlights, TOOL_BLOCKLIST stripping markers, `[STRIPPED]` markers on sys[3] and tool headers when descriptions were proxy-stripped, and DIM_YELLOW_BG pre-strip originals on expand (top-level tool description + per-parameter descriptions).
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

Both are reset when session changes (new proxy log file detected via `find_proxy_log_path`).
