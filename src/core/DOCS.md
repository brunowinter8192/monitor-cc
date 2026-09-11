# src/core/

## Role

Session discovery, polling bookkeeping, and mode dispatch. `monitor.py` discovers the current
project's JSONL session files, tracks which ones are live, and dispatches each `--mode` to the
matching pane package's own loop function (`workers`, `panes.token_pane`, `panes.warnings_pane`,
`proxy_display`). Touch this package when changing polling behaviour, session scoping, or mode
dispatch. Do NOT touch it for pane-specific rendering — that lives in `panes/`, `format/`, or the
dedicated pane packages.

## Public Interface

```python
from src.core import run_monitor    # mode dispatcher — called by workflow.py
```

## Flow

```
workflow.py → run_monitor(project_filter, mode)
  → initialize_file_positions()           # scan ~/.claude/projects, set EOF positions
  → [mode dispatch] → workers | panes.token_pane | panes.warnings_pane | proxy_display loop
```

Every pane loop reads `monitor.active_project_filter`/`active_mode` (and, for the tokens/proxy
family, `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts`) via
`from ..core import monitor as _monitor`. The warnings pane also calls `monitor.monitor_sessions()`
on startup and every poll tick — session-file add/remove tracking only.

## Modules

### modes.py (8 LOC)

**Purpose:** `MODE_*` constants (`MODE_ALL`/`MODE_WARNINGS`/`MODE_TOKENS`/`MODE_WORKERS`/`MODE_PROXY`/`MODE_WORKER_PROXY`).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `monitor.py` only.
**Calls out:** none.

---

### monitor.py (107 LOC)

**Purpose:** Session discovery + mode dispatcher. `run_monitor` sets `active_project_filter`/`active_mode`, calls `initialize_file_positions()`, then dispatches by `mode` to the matching pane package's loop function (lazy import per mode) — raises `ValueError` for any other mode. `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts` resolve the current project's newest non-agent session JSONL. `monitor_sessions()`/`update_session_tracking()` maintain `file_positions` (new/removed session files only).
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`.
**Writes:** mutates `file_positions`, `active_project_filter`, `active_mode` (module-level state).
**Called by:** `workflow.py` (top-level entry); `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_pane.py` (all via `from ..core import monitor as _monitor`).
**Calls out:** none.

---

## State

`monitor.py` owns all module-level state:

| Variable | Type | Mutated by |
|---|---|---|
| `file_positions` | `Dict[Path, int]` | `update_session_tracking` (add/remove on session lifecycle) |
| `active_project_filter` | `str \| None` | `run_monitor()` on startup |
| `active_mode` | `str` | `run_monitor()` on startup |

All pane modules read this state via `from ..core import monitor as _monitor`.

## Gotchas

- `is_agent_file()` filters out subagent JSONLs by path pattern (`agent-*` prefix) — must stay in sync with whatever `session_finder.py` indexes as a subagent file.
- `_get_session_start_ts()` reads the newest main session JSONL and subtracts 10 seconds as the cutoff timestamp `proxy_display` uses for its historical-replay window.
- `monitor_sessions()` only keeps `file_positions` in sync with which session files currently exist — it does not produce any content any pane currently displays. The warnings pane still calls it every poll tick for that bookkeeping side effect.
