# src/workers/

## Role

Worker discovery and per-worker display support. Discovers active Claude Code worker sessions via
tmux, extracts token/context-% stats from their JSONL files, renders the worker-switch header
shared by this pane and `proxy_display/worker_proxy_pane.py`, and owns the worker-tokens pane — an
interactive single-selected-worker cache tracker, the tokens-pane analog for workers. Publishes
the selected worker name via an IPC file for cross-pane coordination. Touch this package when
changing worker discovery, worker status/stat extraction, the worker-switch header, or the
worker-tokens pane display. Do NOT touch it for proxy rendering — `worker_proxy_pane.py` only
reads the IPC selection file and the shared header builder here.

## Public Interface

- `run_worker_tokens_loop` — worker-tokens pane event loop (entry point from `core.monitor`)
- `write_selection(project_filter, worker_name)` — write the selected worker name to the IPC file
  (re-exported from `worker_selection._write_selection`; used by `proxy_display`)

## Flow

tmux session list → `worker_tmux` (discover workers, detect status, find JSONL path,
`attach_worker_stats` for token/context-% liveness) → `worker_switch_header` (shared switch-header
string + click regions, used by both worker panes) → `worker_tokens_pane` (event loop: reads the
IPC-selected worker, incrementally builds that worker's cache turns via `panes.cache_turns`, and
renders via `format.token_format.format_cache_tracker` — the same rendering primitive
`panes/token_pane.py` uses for the main session) → stdout. `worker_selection.py` owns the IPC
path + write, imported by both this package and `proxy_display`.

## Modules

### worker_tmux.py (99 LOC)

**Purpose:** Discover active Claude Code worker sessions via `tmux list-sessions`, detect per-worker status, locate each worker's most recent session JSONL file, and attach token/context-% liveness stats to a worker list.
**Reads:** tmux session list (subprocess); tmux pane/window state for status detection; worker CWD from tmux env; worker JSONL (via `worker_format`'s extractors, inside `attach_worker_stats`).
**Writes:** nothing — returns worker dicts and JSONL paths; `attach_worker_stats` mutates its `workers` argument in place (`tokens`/`context_pct` keys).
**Called by:** `src/workers/worker_tokens_pane.py`, `src/proxy_display/worker_proxy_pane.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### worker_format.py (59 LOC)

**Purpose:** Pure JSONL extraction for one worker — token sums, context-%, and tool-call lists. `_WORKER_CONTEXT_WINDOW = 1000000` — a flat 1M window, since the worker fleet runs exclusively on 1M-context models.
**Reads:** worker JSONL file (full read per call).
**Writes:** nothing — returns a token-summary dict, a context-% int, or a tool-call list.
**Called by:** `src/workers/worker_tmux.py` (`extract_worker_tokens`, `extract_worker_context_pct`, via `attach_worker_stats`).
**Calls out:** none.

---

### worker_selection.py (25 LOC)

**Purpose:** Selection IPC — `get_selection_file_path(project_filter)` builds the `/tmp/monitor_cc_selected_worker_<hash>.txt` path (md5 of the normalized project path, or `'global'` when absent); `_write_selection(project_filter, name)` writes the selected worker name there, or removes the file when `name` is falsy.
**Reads:** nothing.
**Writes:** `/tmp/monitor_cc_selected_worker_<hash>.txt`.
**Called by:** `src/workers/worker_tokens_pane.py`; `src/proxy_display/worker_proxy_pane.py` (`get_selection_file_path`).
**Calls out:** none.

---

### worker_switch_header.py (64 LOC)

**Purpose:** `format_worker_switch_header(workers, current_worker, pane_width, regions_out, label)` — the shared, wrap-aware worker-switcher header string (per-worker marker with status + context-% liveness, color-coded) and its clickable region table (`_register_marker_regions`, one region per physical row a marker straddles). Shared verbatim by both worker panes; `label` is the only thing that differs between them.
**Reads:** parameters only.
**Writes:** nothing — returns a string; mutates `regions_out` in place when given (cleared then rebuilt).
**Called by:** `src/workers/worker_tokens_pane.py`; `src/proxy_display/worker_proxy_pane.py` (imported under the alias `_format_worker_proxy_header`).
**Calls out:** none.

---

### worker_tokens_pane.py (367 LOC)

**Purpose:** Worker-tokens pane event loop — the tokens-pane analog for a single selected worker. 2-row header (search bar + worker-switch header), keyboard/mouse input, periodic data refresh (worker list + liveness stats, IPC-selected worker, incremental cache-turn build), viewport-clipped rendering via `format.token_format.format_cache_tracker`, and the IPC selection-file write when the switch header or a digit key changes the selected worker. Structured drain-refresh-render, mirroring `panes/token_pane.py`'s own shape for the body and `proxy_display/worker_proxy_pane.py`'s own shape for the header/switch mechanics.
**Reads:** the IPC selection file (via `worker_selection.get_selection_file_path`); the selected worker's JSONL (via `worker_tmux.find_worker_jsonl` + `panes.cache_turns.build_cache_turns`); stdin (keyboard/mouse).
**Writes:** ANSI output to stdout (header-overdraw pattern, since the switch header can wrap); selected worker name to the IPC file on switch; `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates its own module-level state (`worker_tokens_expand_states`, `worker_tokens_line_map`, `worker_tokens_scroll_offset`, `_worker_tokens_turns`, `_worker_tokens_workers`, `_worker_tokens_current_name`, `_worker_tokens_search`, `_worker_tokens_nav`, `_worker_tokens_header_regions`).
**Called by:** `src/core/monitor.py` (via `..workers.run_worker_tokens_loop`).
**Calls out:** none.

---

## State

`worker_tokens_pane.py` owns:
- `worker_tokens_expand_states: Dict[tuple, bool]` — expand/collapse state keyed by `(turn_idx, call_idx)`, same shape as `panes/token_pane.py`'s `cache_expand_states` (no per-worker wrapping — only one worker's turns are ever in memory).
- `worker_tokens_scroll_offset: int` — bottom-anchored scroll offset for the cache tracker; reset to 0 on worker switch.
- `_worker_tokens_current_name: Optional[str]` — the worker the pane's own state (turns, expand states, search, scroll) is currently scoped to; a change resets all of it.
- `_worker_tokens_header_regions: Dict[Tuple[int,int,int], str]` — `(start_col,end_col,phys_row) → worker_name`, rebuilt every render from `worker_switch_header.format_worker_switch_header`, shifted by the search-bar row.
- `_worker_tokens_search: search_bar.SearchState` — matches are the plain `(turn_idx, call_idx)` / `('turn', turn_idx)` shape, reusing `panes.token_search.build_token_search_matches` directly (no worker-name wrapping needed).

Mutated exclusively by `run_worker_tokens_loop`'s private helpers — no external mutators.

## Gotchas

- **The all-workers list pane (`worker_pane.py`) and its siblings (`worker_render.py`, `worker_search.py`, `worker_clipboard.py`) are DELETED (2026-09, panesplit milestone).** The user explicitly accepted losing the simultaneous all-workers overview in exchange for two consistent tokens/proxy-shaped windows per worker; the switch header is the only overview left. Do not resurrect a `format_workers_block`-style stacked render — if a future ask wants an at-a-glance multi-worker view again, that is a new design decision, not a revert.
- **The freeze feature ('f' key, `[LIVE]`/`[FROZEN]` badge) is gone with the list pane, not carried forward.** It solved "pause the whole list so I can read it while it churns" — a problem specific to N simultaneously-updating worker blocks. A single-worker tracker doesn't have that problem in the same shape, and freezing one already-selected worker's own view was never requested.
- **Worker-switch now resets pane state, unlike the deleted list pane.** The list had no single "current worker" to switch away from (documented there as a deliberate no-reset design). This pane has exactly one current worker, same as `worker_proxy_pane.py`, so switching resets `worker_tokens_expand_states`, scroll, search, and the cache-turn incremental-read position — mirroring `worker_proxy_pane.py`'s own worker-switch reset.
- `format_worker_switch_header`'s per-marker text (name + status + context-%) is long enough that this pane's real window share (34% of the window, next to `worker-proxy` at 66%) routinely wraps the header across several physical rows even with a handful of workers — `_register_marker_regions` handles this (one region per row segment a marker straddles), verified at pane widths down to 34 in `dev/click_ui/p1_worker_selection_click_probe.py`.
- `_worker_tokens_header_lines` is a module-level cache of the last-rendered header's total line count (search bar + wrapped switch header), read by `_ensure_worker_tokens_match_visible` to estimate the scroll target on search-jump — it is refreshed every render, not recomputed at jump time, mirroring `panes/token_pane.py`'s own fixed-header-size approach but tolerant of the switch header's variable height.
