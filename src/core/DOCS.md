# src/core/

## Role

Session discovery, polling bookkeeping, and mode dispatch. **(2026-09) The main pane and its
whole rendering/classification pipeline were removed** — window 0 is now the tokens pane at full
width, see `process-docs/main_pane/`. `monitor.py` is what's left: it discovers JSONL session
files, tracks which ones are live, and dispatches each `--mode` to its own pane package
(`workers`, `panes.token_pane`, `panes.warnings_pane`, `proxy_display`). Touch this package when
changing polling behaviour, session scoping, or mode dispatch. Do NOT touch it for pane-specific
rendering — that lives in `panes/`, `format/`, or the dedicated pane packages.

## Public Interface

```python
from src.core import run_monitor    # mode dispatcher — called by workflow.py
```

**(2026-09) `monitor_display.py` and `monitor_session.py` removed entirely** — both existed only
to serve the main pane's tool-call classification/rendering pipeline (`process_session_file`,
`display_tool_call`, `display_warning`, `print_session_status`, `render_main_buffer`, `run_main_loop`,
and everything only they used). Their only other caller was the warnings pane's `monitor_sessions()`
call, which never needed the classification output — it always drew `tool_errors` from the proxy's
`_errors` dual-logs, never from this pipeline's `display_warning` (which fed the main pane's own
buffer, now gone). `monitor_sessions()` survives as pure session-file bookkeeping.

## Flow

```
workflow.py → run_monitor(project_filter, mode)
  → initialize_file_positions()           # scan ~/.claude/projects, set EOF positions
  → [mode dispatch] → workers | panes.token_pane | panes.warnings_pane | proxy_display loop
```

Every pane loop reads `monitor.active_project_filter`/`active_mode` (and, for the tokens/proxy
family, `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts`) via
`from ..core import monitor as _monitor`. The warnings pane also calls `monitor.monitor_sessions()`
on startup and every poll tick — session-file add/remove tracking only, not tool-call extraction.

## Modules

### modes.py (8 LOC, new 2026-09, constants-split milestone)

**Purpose:** `MODE_*` constants (`MODE_ALL`/`MODE_WARNINGS`/`MODE_TOKENS`/`MODE_WORKERS`/`MODE_PROXY`/`MODE_WORKER_PROXY`) — split out of `src/constants.py`'s `MODE_*` cluster. `monitor.py` is this cluster's sole importer anywhere in `src/`/`dev/`, so it moved into this package rather than staying at root.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `monitor.py` only.
**Calls out:** nothing.

---

### monitor.py (107 LOC)

**Purpose:** Session discovery + mode dispatcher. `run_monitor` sets `active_project_filter`/
`active_mode`, calls `initialize_file_positions()`, then dispatches by `mode` to the matching pane
package's own loop function (imported lazily, one `elif` per mode) — raises `ValueError` for any
other mode (fail-fast; every mode `workflow.py` can still route here is listed explicitly).
`get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts` resolve the current
project's newest non-agent session JSONL — read by `proxy_display/pane.py`, `panes/token_pane.py`,
`proxy_display/worker_proxy_pane.py`. `monitor_sessions()`/`update_session_tracking()` maintain
`file_positions` (new/removed session files only) — read by the warnings pane on startup and every
poll tick; no other pane consumes this state. `get_file_end_position`/`get_initial_position` (moved
here from the now-deleted `monitor_session.py`) compute where a tracked file's byte offset starts.
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`.
**Writes:** mutates `file_positions`, `active_project_filter`, `active_mode` (module-level state).
**Called by:** `workflow.py` (top-level entry); `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`,
`panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_pane.py` (all via
`from ..core import monitor as _monitor`, reading `active_project_filter`/`active_mode`/
`get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts`/`monitor_sessions`).
**Calls out:** `session_finder`, `jsonl` (`parse_jsonl_lines`, `read_new_lines`, for
`_get_session_start_ts`); `.modes` (`MODE_*`, 2026-09 constants-split milestone — re-pointed from
`..constants`); lazy: `workers`, `panes`, `proxy_display` (mode-dispatch imports).

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

- `is_agent_file()` filters out subagent JSONLs by path pattern — logic must stay in sync with
  `session_finder.py` which indexes them.
- `_get_session_start_ts()` reads the newest main session JSONL and subtracts 10s (comment says
  60s — pre-existing discrepancy, not touched by the 2026-09 main-pane removal) as the cutoff.
  Changing this affects `proxy_display`'s historical-replay window.
- `monitor_sessions()` is a bookkeeping no-op as far as any pane's *displayed content* goes — it
  only keeps `file_positions` in sync with which session files currently exist. The warnings pane
  calls it out of habit from when it fed a shared tool-call pipeline; nothing currently reads the
  result. Kept because `monitor_sessions` is documented pane-facing API (see `panes/DOCS.md`), not
  because anything depends on its side effect today.
- The 24h log janitor sweep (`log_janitor.cleanup_old_jsonl` over `sweep_eligible_specs`) used to
  run from this package's `run_main_loop`. It now runs from `panes/token_pane.py::run_tokens_loop`
  instead — the tokens pane is the always-active, main-checkout-resident pane that replaces the
  main pane's role as the janitor's host (see `process-docs/logging/log_janitor.md` and
  `process-docs/main_pane/`).
