# src/workers/

## Role

Worker discovery and per-worker display support: finds active worker sessions via tmux, extracts token and context stats from their JSONL, provides the shared worker-switch header, and owns the worker-tokens pane for one selected worker. Touch for worker discovery, stats, header or that pane; not for proxy rendering.

## Public Interface

`__init__.py` re-exports the worker-tokens pane loop (entry from `core/monitor.py`) and the selection-file writer (used by `proxy_display`).

## Flow

tmux session list -> `worker_tmux.py` (discovery, status, JSONL path, incremental stats) -> `worker_switch_header.py` (shared header and click regions) -> `worker_tokens_pane.py` (event loop; builds the selected worker's cache turns and renders through `format/token_format.py`) -> stdout. `worker_selection.py` owns the selection IPC file shared with `proxy_display`.

## Modules

### worker_tmux.py (111 LOC)

**Purpose:** discovers worker sessions via tmux, detects status, locates each worker's newest session JSONL and attaches incremental token and context stats.
**Reads:** tmux session, pane and window state; worker JSONL incrementally by byte position.
**Writes:** mutates the worker list and a caller-owned stats cache in place.
**Called by:** `workers/worker_tokens_pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** `tmux` (subprocess CLI).

---

### worker_format.py (32 LOC)

**Purpose:** pure JSONL extraction for one worker: incremental token sum and context percentage.
**Reads:** the worker JSONL file from a caller-supplied byte position.
**Writes:** nothing; returns values.
**Called by:** `workers/worker_tmux.py`.
**Calls out:** none.

---

### worker_selection.py (27 LOC)

**Purpose:** selection IPC: builds the per-project selection file path and writes or removes the selected worker name.
**Reads:** nothing.
**Writes:** the selection file under `/tmp`.
**Called by:** `workers/worker_tokens_pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** none.

---

### worker_switch_header.py (64 LOC)

**Purpose:** shared wrap-aware worker-switcher header string and its clickable region table.
**Reads:** parameters only.
**Writes:** returns a string; fills a caller-supplied region table in place.
**Called by:** `workers/worker_tokens_pane.py`, `proxy_display/worker_proxy_pane.py`.
**Calls out:** none.

---

### worker_tokens_pane.py (392 LOC)

**Purpose:** event loop of the worker-tokens pane: header, input, periodic refresh, viewport rendering and selection-file write on worker switch.
**Reads:** the selection file, the selected worker's JSONL, every listed worker's JSONL for header liveness, stdin.
**Writes:** frames to stdout; selection file on switch; pane error log on exception; its own module-level state.
**Called by:** `core/monitor.py` (via the package export).
**Calls out:** none.

---

## State

`worker_tokens_pane.py` owns all pane state (expand states, scroll, current worker, turns, search, header regions, turn cache, stats cache) and is its only mutator. A worker switch resets everything except the stats cache.
