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
- `find_worker_proxy_log(worker_name)` — resolve proxy log path for a named worker
- `_parse_log_file(path, last_position)` — low-level log file reader
- `format_proxy_block(entries, ...)` — render full proxy pane ANSI string

## Flow

`src/logs/api_requests_*.jsonl` → `parser` (incremental JSONL read, raw_payload extraction → flat entry dicts)
→ `format` (group by turn — turns always expanded, viewport, scroll) → `render_turn` (req rows)
→ `render_sections` + `render_messages` (expanded req detail)
→ `pane` / `worker_proxy_pane` (event loop, stdin → stdout)

**Expand model (flat):** Turns are static info-headers (non-clickable, always visible). Only Req-level and below are expandable. line_map contains only Req-level and deeper keys — one sequential phys_row counter through the visible slice, no nested offsets.

## Modules

### pane.py (133 LOC)

**Purpose:** Event loop for the main proxy pane — reads proxy log incrementally, handles mouse/keyboard input (click expand/collapse, scroll, hover), renders on change.
**Reads:** Module-level state (entries, expand states, scroll offset, hover row, line map); active project filter from shared monitor state; stdin.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_proxy_loop`)
**Calls out:** `input` (click_handler), `panes` (token_pane.build_cache_turns)

---

### worker_proxy_pane.py (194 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches active workers, reads the selected worker's proxy log, handles digit-key worker switching, mouse/keyboard input, renders with worker-switcher header.
**Reads:** Module-level state; live worker list from `workers.worker_tmux`; worker selection IPC file.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..proxy_display.run_worker_proxy_loop`)
**Calls out:** `input` (click_handler), `workers` (worker_tmux), `panes` (token_pane.build_cache_turns)

---

### format.py (205 LOC)

**Purpose:** `format_proxy_block` — groups proxy entries by turn (turns always expanded, turn header key=None), applies scroll/viewport windowing, delegates rendering to `render_turn`, returns `(ansi_string, total_lines)` for scroll math.
**Reads:** Entries list, expand states, line map, hover row, pane dimensions, scroll offset, turns list.
**Writes:** Nothing — returns `(ansi_string, total_lines)` tuple.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`
**Calls out:** `format` (token_format)

---

### parser.py (218 LOC)

**Purpose:** Read and parse proxy log JSONL files — extract rich fields from `raw_payload` (system blocks, tools, messages, schema warnings) into flat entry dicts, then discard raw payload to save memory.
**Reads:** Proxy log JSONL file by project filter or direct path (incremental by byte position).
**Writes:** Nothing — returns `(entry_list, new_position)`.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py`, `src/panes/waste_pane.py`, `src/panes/warnings_pane.py`, `src/metadata/metadata_pane.py`
**Calls out:** —

---

### render_entry.py (200 LOC)

**Purpose:** Render a single proxy request entry (collapsed or expanded) into display lines — shows model, message count, cache breakpoints, change warnings, delta breakdown, and flat per-message list when expanded. Used only in no-turns mode (when turns list is empty). Msg rows are non-clickable (key=None); msg-level expand was removed to keep line_map flat.
**Reads:** Entry dict, all entries (for prev-entry lookup), expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** —

---

### render_turn.py (133 LOC)

**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/tools/messages rendering to section modules.
**Reads:** Group dict, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys, opus_req_num, sub_req_num)` tuple.
**Called by:** `src/proxy_display/format.py`
**Calls out:** —

---

### render_sections.py (156 LOC)

**Purpose:** Render the system blocks section and tools section for an expanded request entry — handles unchanged detection, per-block expand/collapse, change highlights, and TOOL_BLOCKLIST stripping markers.
**Reads:** Entry dict, previous entry, expand states, pane width, modifications list.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** —

---

### render_messages.py (183 LOC)

**Purpose:** Render new/modified/removed messages for an expanded request entry — handles added messages (full block content) and diffs (content_tail), prefers `stripped_msg_removed` over `stripped_msg_originals` for stripped-message display.
**Reads:** Entry dict, previous entry, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** —

---

## State

`pane.py` and `worker_proxy_pane.py` each own independent module-level mutable state:
- entries list, expand states dict, scroll offset, hover row, line map, turns list

Both are reset when session changes (new proxy log file detected via `find_proxy_log_path`).
