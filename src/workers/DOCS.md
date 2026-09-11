# src/workers/

## Role

Workers pane package. Discovers active Claude Code worker sessions via tmux, extracts token and
tool-call data from their JSONL files, renders an interactive TUI pane with expand/collapse and a
per-worker cache-tracker, and publishes the selected worker name via an IPC file for cross-pane
coordination with `proxy_display`. Touch this package when changing worker discovery, worker
status detection, or the workers pane display. Do NOT touch it for proxy rendering — that pane
only reads the IPC selection file.

## Public Interface

- `run_workers_loop` — Workers pane event loop (entry point from `core.monitor`)
- `write_selection(worker_name)` — write the selected worker name to the IPC file (used by `proxy_display`)

## Flow

tmux session list → `worker_tmux` (discover workers, detect status, find JSONL path) →
`worker_format` (extract tokens + tool calls from JSONL, render the block) → `worker_pane` (event
loop, IPC selection-file write → stdout). `worker_pane.py` delegates concern-specific work to
sibling modules: `worker_selection.py` (IPC path + write), `worker_clipboard.py` (clipboard
serialization), `worker_render.py` (pure viewport/row-render + jump-scroll math), `worker_search.py`
(search on_commit reconstruction) — module-level state stays in `worker_pane.py` exclusively.

## Modules

### worker_tmux.py (89 LOC)

**Purpose:** Discover active Claude Code worker sessions via `tmux list-sessions`, detect per-worker status, and locate each worker's most recent session JSONL file.
**Reads:** tmux session list (subprocess); tmux pane/window state for status detection; worker CWD from tmux env.
**Writes:** nothing — returns worker dicts and JSONL paths.
**Called by:** `src/workers/worker_pane.py`, `src/proxy_display/worker_proxy_pane.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### worker_format.py (227 LOC)

**Purpose:** Extract token sums, context-% and tool-call lists from worker JSONL files; render the full workers-pane block (per-worker rows, status, context-%, model, token counts, freeze badge, expanded cache tracker). `_WORKER_CONTEXT_WINDOW = 1000000` — a flat 1M window, since the worker fleet runs exclusively on 1M-context models.
**Reads:** worker JSONL file (full read for token/tool extraction); worker list + expand/scroll state dicts (for rendering).
**Writes:** nothing — returns a token-summary dict, tool-call list, or the formatted TUI string.
**Called by:** `src/workers/worker_pane.py`.
**Calls out:** none.

---

### worker_selection.py (25 LOC)

**Purpose:** Selection IPC — `get_selection_file_path(project_filter)` builds the `/tmp/monitor_cc_selected_worker_<hash>.txt` path (md5 of the normalized project path, or `'global'` when absent); `_write_selection(project_filter, name)` writes the selected worker name there, or removes the file when `name` is falsy.
**Reads:** nothing.
**Writes:** `/tmp/monitor_cc_selected_worker_<hash>.txt`.
**Called by:** `src/workers/worker_pane.py`; `src/proxy_display/worker_proxy_pane.py` (`get_selection_file_path`, via `worker_pane`).
**Calls out:** none.

---

### worker_clipboard.py (34 LOC)

**Purpose:** `_serialize_workers(key, worker_turns)` — full untruncated clipboard text for a worker-header row (`key: str`, identity + turn/call counts) or an expanded cache-call row (`key: (name, turn_idx, call_idx)`, that call's cache stats + content blocks).
**Reads:** parameters only.
**Writes:** nothing — returns a string.
**Called by:** `src/workers/worker_pane.py`.
**Calls out:** none.

---

### worker_render.py (94 LOC)

**Purpose:** Pure viewport/row-rendering + jump-scroll helpers with no module state — every function takes the caller's own dicts/scalars as explicit parameters and either returns a value or mutates a passed-in dict/set in place. `_workers_terminal_size()`, `_compute_viewport(total_lines, content_height, scroll_offset)`, `_render_workers_rows(...)` (the zebra/hover background loop), `_resolve_workers_hover_key(...)`, `apply_scroll(...)`, `compute_jump_scroll_offset(...)`.
**Reads:** parameters only.
**Writes:** nothing directly — mutates `line_map_out`/`cache_line_map_out`/`copy_rows_out`/`worker_scroll_offsets` arguments in place where documented above.
**Called by:** `src/workers/worker_pane.py`.
**Calls out:** none.

---

### worker_search.py (36 LOC)

**Purpose:** `workers_search_on_commit(state, workers, project_filter, pane_width, worker_turns, load_turns_fn, jump_fn)` — the search bar's on_commit body (fires on Enter). `worker_turns` is only populated for currently-expanded workers, so finding matches across all workers requires force-parsing every listed worker's own JSONL via the injected `load_turns_fn` callable; `jump_fn` is likewise injected rather than imported. Match-key shapes: bare `name` (worker-level — text is `name + purpose`), `(name,'turn',turn_idx)`, `(name,turn_idx,call_idx)` — the latter two wrap `panes.token_search.build_token_search_matches`'s own shapes with the worker name.
**Reads:** parameters only.
**Writes:** nothing directly — mutates `state`/`worker_turns` in place; calls `jump_fn()`.
**Called by:** `src/workers/worker_pane.py` (`_handle_workers_search_input`'s on_commit closure).
**Calls out:** none.

---

### worker_pane.py (330 LOC)

**Purpose:** Workers pane event loop — keyboard/mouse input, periodic data refresh, viewport-clipped screen rendering, and the IPC selection-file write for cross-pane coordination. Structured as drain-refresh-render: `run_workers_loop` delegates to `_poll_workers_input`, `_handle_workers_mouse`/`_handle_workers_body_click`, `_handle_workers_key`, `_refresh_workers_data`, `_build_workers_output`. `_load_worker_turns`/`_parse_worker_turns` are the one place doing the `find_worker_jsonl(...)` lookup; both the search-commit reconstruction (`worker_search.py`) and the jump-to-match re-parse call back into this module via injected callables rather than importing it directly. A row click or digit key both toggle expand/collapse AND select the worker (writes the IPC selection file); the freeze badge is a clickable button toggling the module-level freeze flag threaded through the whole loop.
**Reads:** `_monitor.active_project_filter` (shared global state); stdin (keyboard/mouse); worker JSONL files via `worker_format` and directly via `_load_worker_turns`/`_parse_worker_turns` (search reconstruction + jump-time re-parse).
**Writes:** ANSI output to stdout; selected worker name to `/tmp/monitor_cc_selected_worker_<hash>.txt` (via `worker_selection._write_selection`); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `worker_copy_rows`, `_worker_copy_feedback_until`, `_worker_pane_width`, `_worker_header_regions`, `_worker_search`, `worker_expand_states`/`worker_turns`/`worker_scroll_offsets`/`worker_selected_name`.
**Called by:** `src/core/monitor.py` (via `..workers.run_workers_loop`); `src/proxy_display/worker_proxy_pane.py` (imports `get_selection_file_path` — re-exported via this module's own `worker_selection` import — and `write_selection` — re-exported via `src/workers/__init__.py`).
**Calls out:** none.

---

## State

`worker_pane.py` owns:
- `worker_expand_states: Dict[str, bool]` — expand/collapse state keyed by worker name.
- `worker_scroll_offsets: Dict[str, int]` — intra-worker scroll position for the expanded cache-tracker (15-line view); reset to 0 on expand.
- `worker_scroll_offset: int` — dormant pane-level scroll int; kept only as the bottom-anchor for the viewport slice cap.
- `worker_copy_rows: Set[int]` — phys_rows where ⎘/✓ is rendered; cleared+rebuilt each `_build_workers_output` call.
- `_worker_copy_feedback_until: Dict` — mixed-key (`str` name OR `(name,turn_idx,call_idx)` tuple) → expiry float for the ✓ flash.
- `_worker_header_regions: Dict[Tuple[int,int,int], str]` — `(start_col,end_col,phys_row) → 'freeze'`; empty when the freeze badge has scrolled out of the viewport.
- `_worker_search: search_bar.SearchState` — `.matches` holds worker-tagged keys (`str` name / `(name,'turn',turn_idx)` / `(name,turn_idx,call_idx)`).

Mutated exclusively by `run_workers_loop`'s private helpers — no external mutators.
`worker_scroll_offsets` is read by `format_workers_block` in the same process.

## Gotchas

- `worker_scroll_offset` (the pane-level int) is dormant. Wheel events write to `worker_scroll_offsets[name]` (per-worker dict) instead, which `format_cache_tracker` reads to scroll the expanded REQ view. The int only anchors the bottom-anchor slice cap that prevents terminal overflow with many workers, and jump-to-match deliberately never touches it either — if a matched worker is scrolled off the top of a long list, there is no wheel-scroll-up for the outer list to reach it.
- **Safety-net error log:** unhandled exceptions in the render loop append to `/tmp/monitor_cc_error.log` — check this file when the workers pane appears frozen or blank without an obvious error onscreen.
- `worker_search.py`'s `load_turns_fn`/`jump_fn` are injected callables, not direct imports. `worker_pane.find_worker_jsonl` is `dev/pane_search/p7_workers_pane_parity_test.py`'s monkeypatch target — a module that imported `find_worker_jsonl` directly instead of receiving it by reference would not see that patch.
- **No worker-switch reset analog, by design.** Every other search-enabled pane tracks exactly one session/worker and resets search state on switch; this pane shows all workers simultaneously, so there is no single-item switch to reset on. A stale match referencing a since-vanished worker becomes an inert no-op rather than showing wrong data.
- `format_workers_block` prepends two literal spaces before every `format_cache_tracker` line in the nested per-worker view — a `cc_broken` row's `LIGHT_RED_BG` prefix is therefore never at column 0 there. The `LIGHT_RED_BG in line` substring check (not `.startswith`) in `worker_render._render_workers_rows` handles this; switching that check back to a prefix match would silently break cc_broken highlighting only in the nested view.
