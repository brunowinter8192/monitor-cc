# src/workers/

Workers pane subpackage. Discovers active Claude Code worker sessions via tmux, extracts token data
from their JSONL files, and renders an interactive TUI pane with expand/collapse and cache-tracker
per worker.

## worker_tmux.py

**Purpose:** tmux session discovery and worker status detection.
**Input:** Project path string (to derive project name and session prefix).
**Output:** List of worker dicts (`name`, `session`, `status`, `spawned`, `purpose`, `model`);
optional Path to the worker's most recent JSONL file.

Contains:
- `list_workers(project_path)` — queries `tmux list-sessions`, filters by `worker-<project>-` prefix,
  builds worker dict per session
- `detect_worker_status(session)` — checks `#{pane_dead}` + `#{window_activity}` delta to classify
  as `working` / `idle` / `exited` / `unknown`
- `find_worker_jsonl(session_name)` — resolves worker's CWD from tmux, encodes it to the Claude
  projects path, returns newest non-agent JSONL file
- `get_tmux_env(session, var)` — reads a single env var from a tmux session

## worker_format.py

**Purpose:** Worker data extraction and pane rendering.
**Input:** Worker JSONL path (for token extraction); worker list + state dicts (for rendering).
**Output:** Token summary dict; tool call list; formatted TUI string for the workers pane.

Contains:
- `extract_worker_tokens(jsonl_path)` — reads full JSONL, sums output tokens across all assistant
  messages
- `extract_worker_tool_calls(jsonl_path)` — reads full JSONL, collects all tool_use blocks with
  name + input + timestamp
- `format_workers_block(workers, expand_states, ...)` — renders the full workers pane: header,
  per-worker rows with status/model/tokens, expanded cache tracker via `format_cache_tracker()`
- `get_worker_project_name(project_path)` — derives display name, worktree-aware

## worker_pane.py

**Purpose:** Workers pane event loop — keyboard/mouse input, data refresh, screen rendering.
**Input:** `_monitor.active_project_filter` (global state from monitor.py).
**Output:** Writes formatted workers pane to stdout in a continuous loop.

**Event loop** (`run_workers_loop()`):
1. Read keyboard/mouse input: click to expand/collapse, scroll within expanded worker, digit keys 1-9
2. Data refresh every `POLL_INTERVAL` seconds: `list_workers()` → per-worker `extract_worker_tokens()`
   + `extract_cache_turns()` for expanded workers
3. Re-render via `format_workers_block()` only when output changed
4. Selected worker name written to IPC file (`/tmp/monitor_cc_selected_worker_<hash>.txt`) for
   cross-pane coordination with the proxy and metadata panes

**IPC:** `get_selection_file_path()` / `_write_selection()` — shared with proxy_display and
metadata_pane to keep all three panes focused on the same worker.
