# src/workers/

## Role

Workers pane package. Discovers active Claude Code worker sessions via tmux, extracts token and
tool-call data from their JSONL files, renders an interactive TUI pane with expand/collapse and
per-worker cache-tracker, and publishes the selected worker name via an IPC file for cross-pane
coordination with `proxy_display` and `metadata`. Touch this package when changing worker
discovery, worker status detection, or the workers pane display. Do NOT touch for proxy or
metadata rendering — those panes only read the IPC selection file.

## Public Interface

- `run_workers_loop` — Workers pane event loop (entry point from `core.monitor`)
- `write_selection(worker_name)` — write selected worker name to IPC file (used by `proxy_display`)

## Flow

tmux session list → `worker_tmux` (discover workers, detect status, find JSONL path)
→ `worker_format` (extract tokens + tool calls from JSONL, render block)
→ `worker_pane` (event loop, IPC selection file write → stdout)

## Modules

### worker_tmux.py (94 LOC)

**Purpose:** Discover active Claude Code worker sessions via `tmux list-sessions`, detect per-worker status, and locate each worker's most recent session JSONL file.
**Reads:** tmux session list (via subprocess); tmux pane/window state for status detection; worker CWD from tmux env.
**Writes:** Nothing — returns worker dicts and JSONL paths.
**Called by:** `src/workers/worker_pane.py`, `src/proxy_display/worker_proxy_pane.py`
**Calls out:** `session_finder` (encode_project_path)

---

### worker_format.py (170 LOC)

**Purpose:** Extract token sums and tool call lists from worker JSONL files; render the full workers pane block with per-worker rows, status, model, token counts, and expanded cache tracker.
**Reads:** Worker JSONL file (full read for token/tool extraction); worker list + expand/scroll state dicts (for rendering).
**Writes:** Nothing — returns token summary dict, tool call list, or formatted TUI string.
**Called by:** `src/workers/worker_pane.py`
**Calls out:** `jsonl`, `format` (token_format)

---

### worker_pane.py (163 LOC)

**Purpose:** Workers pane event loop — keyboard/mouse input, periodic data refresh, viewport-clipped screen rendering (bottom-anchored, clips all_lines to pane_height so phys_row always equals terminal row), and IPC selection file write for cross-pane coordination.
**Reads:** `_monitor.active_project_filter` (shared global state); stdin (keyboard/mouse); worker JSONL files via `worker_format`.
**Writes:** ANSI output to stdout; selected worker name to `/tmp/monitor_cc_selected_worker_<hash>.txt`.
**Called by:** `src/core/monitor.py` (via `..workers.run_workers_loop`); `src/proxy_display/worker_proxy_pane.py` (imports `get_selection_file_path`, `write_selection`)
**Calls out:** `jsonl`, `input` (click_handler)

---

## State

`worker_pane.py` owns two module-level mutable dicts:
- `worker_expand_states: Dict[str, bool]` — expand/collapse state keyed by worker name
- `worker_scroll_offsets: Dict[str, int]` — scroll position keyed by worker name

Mutated exclusively by `run_workers_loop`. Read by `format_workers_block` in the same process.
