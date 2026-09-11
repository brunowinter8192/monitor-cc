# src/proxy_display/

## Role

Proxy pane TUI package. Reads mitmproxy forwarded-delta entries from the runtime dual-log
directory (gitignored, not present in a fresh checkout — api_requests_*_forwarded.jsonl under
src/logs/dual_log/), reconstructs per-request system/tools/messages via delta accumulation, and
renders an interactive expand/collapse display showing API request structure (model, message
counts, system/tools/messages detail). Also reads the sibling stripped/injected/original
dual-logs to drive a yellow (`DIM_YELLOW_BG`) / green (`DIM_GREEN_BG`) overlay showing what the proxy stripped and injected
per request, including expandable whole-stripped-tool original definitions. Runs two event loops
— one for the main session proxy log (`pane.py`), one for the selected worker's proxy log
(`worker_proxy_pane.py`) — both carry the full dual-log overlay and a permanent row-1 search bar.
Touch this package when changing proxy pane display logic or the forwarded-log field extraction.
Do NOT touch for the proxy modification pipeline (strip/inject rule logic) — that lives in
`src/proxy/`.

## Public Interface

- `run_proxy_loop` — main proxy pane event loop, entry point from `core.monitor`
- `run_worker_proxy_loop` — worker proxy pane event loop, entry point from `core.monitor`
- `find_worker_proxy_log(worker_name, project_filter=None)` — resolve proxy log path for a named worker; returns `None` if no match or `project_filter` absent — lives in `parser.py`
- `format_proxy_block(entries, ...)` — render full proxy pane ANSI string, returns `(ansi_string, total_lines)` — lives in `format.py`

Other public entry points not re-exported from `__init__.py`: `parser.find_proxy_log_path`,
`parser.find_errors_log_path`, `parser.find_response_log_path`, `parser.proxy_session_id_for_project`,
`parser.get_proxy_session_start_ts`, `forwarded_parser.parse_proxy_log_forwarded`,
`side_logs.read_response_log`, `side_logs.scan_worker_errors_logs` — imported directly by
`src/panes/token_pane.py` and `src/panes/warnings_pane.py`.

## Flow

`api_requests_*_forwarded.jsonl` → `forwarded_parser._parse_forwarded_log` (incremental JSONL
read, per-model-family delta accumulation, deque-bounded to the last `PROXY_MESSAGES_KEEP_LAST`
entries — older entries carry `messages=None` until lazy-loaded)
→ `pane.py` / `worker_proxy_pane.py` (extend entries, attach dual-log overlay references via
`proxy_pane_shared._accumulate_dual_logs_and_attach`)
→ `format.format_proxy_block` (group by turn, viewport/scroll, row backgrounds)
→ `render_turn` (per-REQ header + expand dispatch) → `render_sections` / `render_sections_system`
/ `render_messages` (expanded request detail — system, tools, fields, messages)
→ stdout (direct ANSI write, tmux pane).

On expand-click or search-Enter, `forwarded_parser._lazy_load_messages_forwarded` /
`reconstruct_all_messages` replay the forwarded stream from byte 0, matched by `flow_id`, to
populate `messages` for entries the deque window dropped.

## Modules

### pane.py (327 LOC)

**Purpose:** Event loop for the main proxy pane — reads the `_forwarded` dual-log incrementally, handles mouse (click expand/collapse, scroll, hover, copy, search) and keyboard input (search, undo, `n`/`N`), renders on change via the drain-refresh-render pattern.
**Reads:** Module-level state; active project filter from `core.monitor`; stdin (keypresses, mouse events).
**Writes:** ANSI output to stdout (direct tmux pane write); clipboard via `copy_to_clipboard`; `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates its own module-level state (entries, expand states, scroll/hover, search state, undo stack, dual-log accumulators).
**Called by:** `src/proxy_display/__init__.py`, `src/core/monitor.py` (lazy import, mode dispatch)
**Calls out:** `input.click_handler` (keypress/mouse/clipboard primitives), `panes.cache_turns` (`build_cache_turns`), `ram_audit` (`register_ram_dump`), `pane_error_log` (`log_pane_error`), `search_bar` (`SearchState` and search-bar mechanics)

---

### worker_proxy_pane.py (332 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches the active worker list, reads the selected worker's `_forwarded` dual-log, handles digit-key and header-click worker switching, mouse/keyboard input, renders with a 2-row header (search bar + worker-switcher). Force-reload-or-tick refresh gate.
**Reads:** Module-level state; live worker list from `workers.worker_tmux`; worker selection IPC file (`workers.worker_pane.get_selection_file_path`); stdin.
**Writes:** ANSI output to stdout (overdraw pattern: body print + header overdraw); clipboard via `copy_to_clipboard`; worker selection IPC file via `workers.write_selection`; `/tmp/monitor_cc_error.log` on caught exception; mutates its own module-level state.
**Called by:** `src/proxy_display/__init__.py`, `src/core/monitor.py` (lazy import, mode dispatch)
**Calls out:** `input.click_handler`, `workers.worker_tmux` (`find_worker_jsonl`, `list_workers`), `workers.worker_pane` (`get_selection_file_path`), `workers` (`write_selection`), `panes.cache_turns` (`build_cache_turns`), `utils` (`visual_line_count`), `ram_audit` (`register_ram_dump`), `pane_error_log` (`log_pane_error`), `search_bar`

---

### proxy_pane_shared.py (228 LOC)

**Purpose:** Mechanics shared by both proxy panes (`pane.py`, `worker_proxy_pane.py`), each function parameterized by explicit arguments — never reads either pane's own module-level globals. Covers the worker-switcher header builder, key/entry-idx resolution, copy-text serialization, expand+lazy-load toggling, dual-log accumulate-and-attach, search-on-commit, scroll/hover dispatch, and render+scroll+row-shift.
**Reads:** Parameters only.
**Writes:** Nothing — returns values; several functions mutate an argument in place (`entries`, `line_map`, `copy_rows`, accumulator dicts) as documented per function, never a name outside the parameter list.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py` exclusively
**Calls out:** `colors` (`RESET`, `YELLOW`, `DIM`, `WHITE`), `search_bar` (`SearchState`, `handle_search_mouse_motion`), `utils` (`_ANSI_ESCAPE_RE`)

---

### format.py (180 LOC)

**Purpose:** `format_proxy_block` — groups proxy entries by turn (turns always expanded, no turn-level header row), applies scroll/viewport windowing, delegates row rendering to `render_turn`, applies the row-background priority chain, returns `(ansi_string, total_lines)`. Also owns `_is_standalone_entry` (haiku or zero-context sidecar detection, used by backward walks across the package) and the REQ-numbering helpers `_fmt_effort`/`_fmt_thinking_budget`.
**Reads:** Entries list, expand states, line map, hover row, pane dimensions, scroll offset, turns list.
**Writes:** Nothing — returns `(ansi_string, total_lines)` tuple; mutates the `line_map`/`copy_rows_out`/`item_positions_out` arguments when given.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/render_turn.py` (`_is_standalone_entry`, `_shorten_model`, `_format_k`, `_fmt_thinking_budget`, `_fmt_effort`), `src/proxy_display/search.py` (`_is_standalone_entry`), `src/proxy_display/proxy_pane_shared.py` (`_is_standalone_entry`), `src/proxy_display/render_sections.py` (`_format_k`), `src/proxy_display/render_sections_system.py` (`_format_k`), `src/proxy_display/__init__.py`
**Calls out:** `format.token_format` (`_format_k`), `search_bar` (`_BG_RESTORE_SENTINEL`, `resolve_bg_restore`)

---

### forwarded_parser.py (274 LOC)

**Purpose:** Forwarded-log delta reconstruction — parses `_forwarded` dual-log JSONL and rebuilds per-request entries (system/tools/messages via index-keyed delta application), computes `has_thinking_delta`, stamps `diff_from_prev`. Leaf module — does not import from `parser.py` (holds its own copy of `_proxy_session_id_for_project` to avoid a circular import).
**Reads:** `_forwarded` dual-log JSONL files (incremental by byte position).
**Writes:** Nothing — returns `(entry_list, new_position)`, `True`/`False`, or a `{flow_id: messages}` dict.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/parser.py` (`_proxy_session_id_for_project`), `src/proxy_display/proxy_pane_shared.py` (`_lazy_load_messages_forwarded`, `reconstruct_all_messages`), `src/proxy_display/dual_log_accumulator.py` (`_infer_model_family`), `src/dual_log_cli/project_map.py` (`_proxy_session_id_for_project`)
**Calls out:** `proxy.message_summary` (`_summarize_message`), `proxy.logging` (`_compute_diff`)

---

### parser.py (104 LOC)

**Purpose:** Proxy log path resolution — marker-file-based resolution of the current proxy session's `_forwarded`/`_stripped`/`_injected`/`_original`/`_errors`/`_response` log paths, and worker log discovery via glob.
**Reads:** `.proxy_session_*` marker files under the runtime log directory (src/logs/, gitignored).
**Writes:** Nothing — returns path objects or a session-id string.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/proxy_display/proxy_pane_shared.py` (`_find_dual_log_paths`), `src/proxy_display/__init__.py` (`find_worker_proxy_log`), `src/panes/warnings_pane.py` (`find_errors_log_path`, `proxy_session_id_for_project`, `get_proxy_session_start_ts`), `src/panes/token_pane.py` (`find_response_log_path`)
**Calls out:** `forwarded_parser` (`_proxy_session_id_for_project`)

---

### proxy_badge.py (81 LOC)

**Purpose:** REQ-header strip/inject badge logic and the total_tokens-nuke text-shape detection it depends on. `badge_flags(entry) -> (show_strip, show_inject)` coordinates the stripped and injected dual-log sides by `flow_id` so that a total_tokens nuke (which injects the same literal `"."` as a real nag/deferred/date-changed nuke) is the one class that shows neither badge word.
**Reads:** Entry dicts (`badge_flags`) or raw delta values (everything else) — parameters only, no module state.
**Writes:** Nothing — returns bools, a 2-tuple, or an int.
**Called by:** `src/proxy_display/dual_log_accumulator.py` (`_is_total_tokens_nuke`, `_msgs_delta_is_substantial`), `src/proxy_display/render_turn.py` (`badge_flags`), `src/proxy_display/format.py` (`_chars_to_tokens`)
**Calls out:** stdlib only (`re`)

---

### dual_log_accumulator.py (120 LOC)

**Purpose:** Dual-log overlay accumulation — tails `_stripped`/`_injected`/`_original` and builds the per-family accumulator state both panes' entries hold references into. `accumulate_original_tools` keeps a latest-snapshot `{tool_name -> tool_def}` map per family (the `_original` log is a full-snapshot log, not delta-encoded). `accumulate_dual_log` mutates its accumulator dict in place (`.clear()`+`.update()`, preserving Python references held by pane entries), maintaining per-flow lookup dicts (`_has_content_by_flow_id`, `_msg_idx_by_flow_id`, `_sys_idx_by_flow_id`, `_tool_name_by_flow_id`, `_lag_msg_idx_by_flow_id`) that back the REQ-header badge and the flow-scoped span lookup in `render_messages._lookup_spans`.
**Reads:** `_stripped`/`_injected`/`_original` dual-log JSONL files (incremental by byte position).
**Writes:** Nothing — returns the new file position; mutates the `acc_by_family` argument in place.
**Called by:** `src/proxy_display/pane.py` (`accumulate_original_tools`), `src/proxy_display/proxy_pane_shared.py` (`accumulate_dual_log`), `src/dual_log_cli/overlay.py` (`accumulate_dual_log`, its own independent accumulator per call — never shares state with the panes')
**Calls out:** none beyond project modules

---

### side_logs.py (79 LOC)

**Purpose:** `_response`/`_errors` side-log readers. `read_response_log` reads `_response` entries incrementally (`{request_id: headers_dict}`). `scan_worker_errors_logs` globs worker `_errors` dual-logs and reads them incrementally by byte position.
**Reads:** `_response`/`_errors` dual-log JSONL files (incremental by byte position).
**Writes:** Nothing — returns tuples.
**Called by:** `src/panes/token_pane.py` (`read_response_log`, lazy import), `src/panes/warnings_pane.py` (`scan_worker_errors_logs`, lazy import)
**Calls out:** stdlib only (`json`, `os`, `pathlib`)

---

### render_turn.py (152 LOC)

**Purpose:** Renders all per-request rows for an expanded turn group — REQ-header line (`▶/▼ #N model Nmsg [eff:X] [think:Nk] [mods] [warns] [tag badge]`), request numbering (`#N` fresh vs `#N.M` retry, `H`/`S` for standalone sidecars), and dispatch into the expanded-request section renderers.
**Reads:** Group dict, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys, opus_req_num, sub_req_num)` tuple.
**Called by:** `src/proxy_display/format.py`, `src/proxy_display/search.py` (`_render_req_expanded`, `_resolve_prev_same_family`)
**Calls out:** `render_messages` (`_aggregate_req_buckets`), `render_sections` (`render_fields_delta`, `render_beta`, `render_directives`, `render_tools`), `render_sections_system` (`render_system_blocks`), `format` (`_BG_RESTORE_SENTINEL`), `utils` (`highlight_query_in_line`)

---

### render_sections.py (315 LOC)

**Purpose:** Renders tools, fields-delta, beta-flags, and directives sections for an expanded request entry. Tools rendering shares the dual-color sentinel (`use_dual = '_stripped_spans' in entry`) with `render_sections_system.py`: the new path reads `entry['_stripped_spans']`/`entry['_injected_spans']` span data, the legacy path (worker pane, or entries without dual-log attachment) uses the old side-channel fields. Whole-stripped tools (blocklist-removed entirely, not just desc-changed) are expandable via `_render_whole_stripped_tool`, sourcing the original definition from `entry['_original_tools_by_name']` — falls back to a `(original definition unavailable)` line when absent (worker pane never attaches this field).
**Reads:** Entry dict, previous entry, expand states, pane width, modifications list.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`, `dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py` (`_render_whole_stripped_tool`, `render_tools`)
**Calls out:** `render_line_helpers` (`_emit_text_lines`, `_emit_span_lines`, `_emit_inline_spans`)

---

### render_sections_system.py (101 LOC)

**Purpose:** `render_system_blocks` — the system-blocks section of an expanded request entry. Per-block delta visibility is content-based (`sb['preview'] == prev.get('preview')`); a first request shows all blocks, a later request skips unchanged blocks entirely. Block header color: yellow when a strip span is present, green when an inject span is present, gray otherwise.
**Reads:** Entry dict, previous entry, expand states, modifications list.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** `format` (`_format_k`), `render_line_helpers` (`_emit_text_lines`, `_emit_span_lines`, `_emit_inline_spans`)

---

### render_line_helpers.py (31 LOC)

**Purpose:** Shared line-emission primitives used by `render_sections.py` and `render_sections_system.py` — split text on `\n`, `expandtabs(8)`, emit one background-colored line per raw line with a `None` key. `_emit_text_lines` is the base case; `_emit_span_lines` applies the same background to every chunk in a flat span list; `_emit_inline_spans` renders the `(tag, text)` inline-diff shape, coloring only `tag == "injected"` chunks. Utility module — no ORCHESTRATOR/FUNCTIONS split, all three functions are equally primitive.
**Reads:** Parameters only.
**Writes:** Nothing — returns `(lines, keys)` tuples.
**Called by:** `src/proxy_display/render_sections.py`, `src/proxy_display/render_sections_system.py`
**Calls out:** `colors` (`SOFT_RESET`, `DIM`)

---

### render_messages.py (281 LOC)

**Purpose:** Renders new/modified/removed messages for an expanded request entry. `render_messages()` dispatches to `_render_new_messages` (when the message count grew) or `_render_modified_messages` (retry/abort re-send) — the request's payload delta is the only source of rendered message content. Span content rendering (inline new-format vs. legacy stacked) goes through the shared `_render_span_content`. `_lookup_spans` scopes the shared, cumulative `_stripped_spans`/`_injected_spans` accumulator dicts to the entry's own `flow_id` via the `_strip_msgs_lookup`/`_inject_msgs_lookup`/`_lag_msgs_lookup` reference sets, preventing a later request's overwrite of a message index from rendering under an earlier/neighbor request. Thinking blocks (`btype == 'thinking'`) get their own collapsed-by-default drill-down (`('think', entry_idx, msg_idx, bidx)` key) with word-wrapped content via `utils.wrap_visible`.
**Reads:** Entry dict, previous entry, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** `proxy.strip_vocab` (`attribute_chunk`, `classify_tags`, `code_for_rule`, `classify_req`), `utils` (`wrap_visible`)

---

### search.py (24 LOC)

**Purpose:** `build_search_matches(query, entries, expand_states, pane_width)` — the ordered list of entry_idx whose expanded-view content matches `query` (case-insensitive). Calls `render_turn._render_req_expanded` FORCE-EXPANDED for every entry (ignoring that entry's own collapsed/expanded state, so a currently-collapsed request can still match) using the real render function rather than a duplicated serializer, so a match can never diverge from what the pane actually renders. Requires `entry['messages']` populated on every entry — the caller runs `forwarded_parser.reconstruct_all_messages` first.
**Reads:** Entries list (requires `messages` populated), expand states, pane width — parameters only, no module state.
**Writes:** Nothing — returns `List[int]`.
**Called by:** `src/proxy_display/proxy_pane_shared.py` (`build_search_matches`, inside `_run_pane_search`, itself called from both panes' search-on-commit)
**Calls out:** `utils` (`_ANSI_ESCAPE_RE`)

---

## State

`pane.py` and `worker_proxy_pane.py` each own independent module-level mutable state — entries
list, expand states dict, scroll offset, hover row, line map, turns list, current log path,
last-rendered pane width, copy-row set, copy-feedback timers, and an undo stack (`pane.py` only,
capped at 200).

**Search state** — each pane owns one `search_bar.SearchState` instance (`_proxy_search` /
`_worker_proxy_search`): query text, focus, ordered match list, match set, current-match index,
and drag-select fields. Rebuilt on every Enter via `proxy_pane_shared._run_pane_search` (never
gated on query-unchanged — the one-sweep reconstruction is cheap enough to always re-run).
Cleared via `search_bar.handle_search_cancel(state)` on session/worker change, NOT on the hourly
reparse (entry_idx-keyed expand/search state assumes stable re-indexing across a same-file
reparse). Drag-select and click-elsewhere clearing go through `search_bar.clear_selection(state)`,
called directly from each pane's own mouse handler.

**Dual-log accumulator** (both panes) — `_proxy_acc_stripped`/`_proxy_acc_injected` and their
worker-pane equivalents are `{family: {...}}` dicts mutated in place by
`dual_log_accumulator.accumulate_dual_log`; every parsed entry holds a REFERENCE (not a copy) to
its family's accumulator dict plus the per-flow lookup sub-dicts, so late-arriving delta updates
propagate to already-rendered entries automatically. Reset (`.clear()`, byte positions to 0) on
session/worker change and on the hourly reparse trigger.

**Whole-stripped tool original-def accumulator** (`pane.py` only) — `_proxy_acc_original`
(`{family -> {tool_name -> tool_def}}`), fed from the `_original` log via
`dual_log_accumulator.accumulate_original_tools`, latest-snapshot overwrite (not merge — tool
defs are stable within a session). `worker_proxy_pane.py` has no equivalent; a whole-stripped
tool row there always shows the `(original definition unavailable)` fallback.

**Lazy-reload invariant:** an entry outside the `PROXY_MESSAGES_KEEP_LAST` tail window and not in
`expand_states` has `messages=None` (stripped by `_parse_forwarded_log`). On expand-click or
search-match, `_lazy_load_messages_forwarded`/`reconstruct_all_messages` replay the forwarded
stream from byte 0, matched by `flow_id`, to repopulate it.

## Gotchas

- `PROXY_MESSAGES_KEEP_LAST = 10` — only the last N parsed entries retain `messages`; older
  entries are lazy-loaded on demand. `PROXY_REPARSE_INTERVAL_SECONDS = 3600` — hourly full
  reparse resets byte positions and accumulators but NOT expand/search state.
- `flow_id`, not `_fwd_req_idx`, is the stable cross-call correlation key. `_fwd_req_idx` resets
  to 0 on every `_parse_forwarded_log` call — it is unique only within one incremental batch, not
  across the polling session. Using it as a dict key across separate parse calls silently loads
  the wrong entry's content.
- `ZEBRA_BG_A = ''` is a valid "no override" background value, not "nothing". `resolve_bg_restore`
  must substitute an explicit `\033[49m` for it when closing a search-highlight span, or the
  highlight background floods the rest of the row to the trailing `\033[K`.
- `_BG_RESTORE_SENTINEL = '\033[999m'` (out-of-range but syntactically valid SGR code) stands in
  for "resume the row's real background" at embed time in `render_turn.py`, since that module
  doesn't know `chosen_bg` (zebra/hover/strip/collision) until `format._apply_row_backgrounds`
  computes it; `utils._ANSI_ESCAPE_RE` strips the sentinel as zero-width wherever visible-length
  math (padding, truncation) already runs.
- A trailing-message total_tokens strip is attributed one request LATE by the delta writer (CC
  hangs the cache-control breakpoint on the last message, so a fresh trailing system message
  arrives list-shaped and produces no diff op on the request that actually stripped it).
  `dual_log_accumulator._apply_lag_correction` re-attributes it to the correct flow via
  `_lag_msg_idx_by_flow_id`, guarded by `proxy_badge._is_total_tokens_nuke` matching the previous
  line's trailing index. This guard is load-bearing: without it, a mid-conversation nag/deferred
  nuke that lands on an index that was an earlier request's trailing message would bleed into the
  wrong request's rendered spans.
- A strip landing outside the request's own payload delta (task-tools nag, deferred-tools notice,
  date-changed) is INVISIBLE in the expanded body — only the REQ-header `strip`/`inject` badge
  words show it happened. The original text is only recoverable via the dual-log CLI
  (`duallog expand`), not in the pane. Do not "fix" this by loosening `_lookup_spans`' flow
  scoping — that reintroduces cross-request span bleed.
- `_is_total_tokens_nuke_text`'s catalogued-nudge-paragraph matching (`_TOTAL_TOKENS_NUDGE_PARAGRAPHS`)
  is deliberately NOT future-proof against a new, uncatalogued CC nudge sentence: an unrecognized
  sentence fails the test and the request stays badged (fails toward showing it) rather than being
  silently absorbed as quiet.
- `parser.get_proxy_session_start_ts` treats a `.proxy_session_<id>` marker file older than 24h as
  stale and returns `time.time()` instead of its mtime.
