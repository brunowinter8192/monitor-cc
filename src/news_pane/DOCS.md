# src/news_pane/

## Role

Standalone tmux pane pair that controls and observes the CoinDesk news ingestion pipeline of the websearch project. The left pane shows collection stats and a run button; the right pane tails the pipeline log. No dependency on `core/monitor.py`. Do not touch for the pipeline itself.

## Public Interface

Two entry points, called by `workflow.py`: the left control pane loop in `pane.py` and the right log-tail loop in `log_pane.py`.

## Flow

Left pane: poll tick → `rag-cli` collection stats and last-run file → render; a click on the run button launches the pipeline subprocess.
Right pane: poll tick → `log_parser.py` finds the newest log, extracts the current run and filters events → top-anchored render.

## Modules

### pane.py (303 LOC)

**Purpose:** Left control pane loop with stats display, mouse and keyboard dispatch, pipeline launch and search bar.
**Reads:** `rag-cli` collection stats; the last-run file; the pipeline process handle.
**Writes:** stdout frames; pane error log; its process handle, button regions and search state.
**Called by:** `workflow.py`.
**Calls out:** `rag-cli`, the websearch project's pipeline

---

### log_pane.py (85 LOC)

**Purpose:** Right log-tail pane loop that filters the current run's events and renders them top-anchored.
**Reads:** the newest pipeline log via `log_parser.py`.
**Writes:** stdout frames; pane error log.
**Called by:** `workflow.py`.
**Calls out:** none

---

### log_parser.py (78 LOC)

**Purpose:** Log parsing helpers plus the package's path constants for the websearch project, log directory and last-run file.
**Reads:** the pipeline log files and the last-run file.
**Writes:** pane error log on an unreadable log file.
**Called by:** `pane.py`, `log_pane.py`.
**Calls out:** none

---

## State

Only `pane.py` holds state: the pipeline process handle, the clickable button regions and the search state. The log pane and parser are stateless. Behavior notes are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file).
