# src/core/

## Role

Session discovery and mode dispatch: finds the current project's JSONL session files and hands each `--mode` to the matching pane package's loop. Touch for polling, session scoping or mode dispatch; not for pane rendering, which lives in `panes/`, `format/` or the dedicated pane packages.

## Public Interface

```python
from src.core import run_monitor    # mode dispatcher — called by workflow.py
```

## Flow

```
workflow.py → run_monitor (project filter, mode)
  → [mode dispatch] → workers | panes.token_pane | panes.warnings_pane | proxy_display loop
```

Every pane loop reads the active project filter, the active mode and the session lookups of
`monitor.py` through a lazy `from ..core import monitor as _monitor`.

## Modules

### modes.py (8 LOC)

**Purpose:** the set of valid mode identifiers accepted by the dispatcher.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `monitor.py` only.
**Calls out:** none.

---

### monitor.py (64 LOC)

**Purpose:** session discovery and mode dispatcher; lazily imports the pane package for the given mode and resolves the newest main session file.
**Reads:** `~/.claude/projects/**/*.jsonl` via `session_finder`.
**Writes:** mutates its module-level state (active project filter, active mode).
**Called by:** `workflow.py` (top-level entry); `proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`, `panes/token_pane.py`, `panes/warnings_pane.py`, `workers/worker_tokens_pane.py` (all via `from ..core import monitor as _monitor`).
**Calls out:** none.

---

## State

`monitor.py` owns the module-level state (active project filter and active mode). It is set once at startup by the dispatcher; all pane modules only read it.
