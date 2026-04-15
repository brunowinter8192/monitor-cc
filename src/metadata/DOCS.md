# src/metadata/

Metadata pane — reads proxy log entries and displays API configuration state (model, thinking, cache markers, tool counts, modifications).

## Modules

## metadata_format.py

**Purpose:** Format the latest proxy log entry into a multi-section ANSI display showing SYSTEM, TOOLS, CONFIG, CACHE MARKERS, and SESSION sections. Tracks state across calls to highlight changed values in red.

**Input:** Proxy log entry dict (from `proxy_display.parse_proxy_log`); separate state dicts for main and worker panes.

**Output:** Multi-line ANSI string for the metadata pane.

---

## metadata_pane.py

**Purpose:** Two event loops — `run_metadata_loop` (main proxy log) and `run_worker_metadata_loop` (selected worker's proxy log). Polls on `POLL_INTERVAL`, renders formatted metadata block on change.

**Input:** Shared monitor state (project filter, session timestamp). Worker loop reads selection from `worker_pane.get_selection_file_path()`.

**Output:** ANSI screen output written to stdout (direct tmux pane write).
