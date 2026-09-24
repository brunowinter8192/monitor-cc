# src/core/

## Role

Session discovery and mode dispatch. `monitor.py` discovers the current
project's JSONL session files and dispatches each `--mode` to the
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
  → [mode dispatch] → workers | panes.token_pane | panes.warnings_pane | proxy_display loop
```

Every pane loop reads `monitor.active_project_filter`/`active_mode` (and, for the tokens/proxy
family, `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts`) via
`from ..core import monitor as _monitor`.

## Modules

### modes.py (8 LOC)

**Purpose:** `MODE_*` constants (`MODE_ALL`/`MODE_WARNINGS`/`MODE_TOKENS`/`MODE_WORKER_TOKENS`/`MODE_PROXY`/`MODE_WORKER_PROXY`).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `monitor.py` only.
**Calls out:** none.

---

### monitor.py (64 LOC)

**Purpose:** Session discovery + mode dispatcher. `run_monitor` sets `active_project_filter`/`active_mode`, then dispatches by `mode` to the matching pane package's loop function (lazy import per mode) — raises `ValueError` for any other mode. `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts` resolve the current project's newest non-agent session JSONL.
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`.
**Writes:** mutates `active_project_filter`, `active_mode` (module-level state).
**Called by:** `workflow.py` (top-level entry); `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_tokens_pane.py` (all via `from ..core import monitor as _monitor`).
**Calls out:** none.

---

## State

`monitor.py` owns all module-level state:

| Variable | Type | Mutated by |
|---|---|---|
| `active_project_filter` | `str \| None` | `run_monitor()` on startup |
| `active_mode` | `str` | `run_monitor()` on startup |

All pane modules read this state via `from ..core import monitor as _monitor`.

## Gotchas

- `is_agent_file()` filters out subagent JSONLs by path pattern (`agent-*` prefix) — must stay in sync with whatever `session_finder.py` indexes as a subagent file.
- `_get_session_start_ts()` reads the newest main session JSONL and subtracts 10 seconds as the cutoff timestamp `proxy_display` uses for its historical-replay window.
