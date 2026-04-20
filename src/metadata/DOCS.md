# src/metadata/

## Role

Metadata pane package. Reads the latest proxy log entry and renders a multi-section ANSI display
of the current API configuration state (model, thinking, cache breakpoints, tool counts,
modifications, session info). Runs two independent event loops — one for the main session, one
for the currently selected worker. Touch this package when changing metadata display sections or
the change-highlight logic. Do NOT touch for proxy log parsing — that lives in `proxy_display`.

## Public Interface

- `run_metadata_loop` — main metadata pane event loop (entry point from `core.monitor`)
- `run_worker_metadata_loop` — worker metadata pane event loop (entry point from `core.monitor`)

## Flow

Proxy log file → `proxy_display.parse_proxy_log` (incremental read)
→ `metadata_format._format_metadata` (section render with state diff → changed values highlighted red)
→ stdout

## Modules

### metadata_format.py (196 LOC)

**Purpose:** Format the latest proxy log entry into a multi-section ANSI display (SYSTEM, TOOLS, CONFIG, CACHE MARKERS, SESSION); tracks previous values in module-level state to highlight changes in red.
**Reads:** Proxy log entry dict (from `proxy_display.parse_proxy_log`); `_prev_values` / `_worker_prev_values` module-level state.
**Writes:** Multi-line ANSI string; mutates `_prev_values` / `_worker_prev_values` after each render.
**Called by:** `src/metadata/metadata_pane.py`
**Calls out:** `format` (token_format)

---

### metadata_pane.py (100 LOC)

**Purpose:** Two event loops — `run_metadata_loop` for the main proxy log and `run_worker_metadata_loop` for the selected worker's proxy log; polls on `POLL_INTERVAL`, renders on change.
**Reads:** Shared monitor state (project filter, session timestamp); worker selection file via `workers.worker_pane.get_selection_file_path()`; proxy log via `proxy_display`.
**Writes:** ANSI output to stdout (direct tmux pane write).
**Called by:** `src/core/monitor.py` (via `..metadata.run_metadata_loop` and `..metadata.run_worker_metadata_loop`)
**Calls out:** `proxy_display`, `workers` (worker_pane.get_selection_file_path)

---

## State

`metadata_format.py`:
- `_prev_values: dict` — previous display values for main pane change highlighting
- `_worker_prev_values: dict` — previous display values for worker pane change highlighting

`metadata_pane.py`:
- `_meta_log_position: int`, `_meta_entries: list` — incremental read state for main loop
- `_worker_meta_log_position: int`, `_worker_meta_entries: list` — incremental read state for worker loop
- `_worker_meta_last_name: Optional[str]` — detects worker switch to reset state
