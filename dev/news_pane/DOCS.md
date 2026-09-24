# dev/news_pane/

## Role
Regression checks for the failure paths of `src/news_pane/`. Touch when changing the rag-cli fetch notes, the last-run read or the running state.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/news_pane/fetch_and_running_checks.py`.

## Flow
A fake `rag-cli` on PATH and a temp pane error log drive the count fetchers, the last-run read and the running-state check; each check prints pass or fail.

## Modules

### fetch_and_running_checks.py (134 LOC)

**Purpose:** Proves rag-cli failures return None with one note per state change, only a missing file means no last run, running state comes from the handle.
**Reads:** nothing external; fake `rag-cli` and log in a temp dir.
**Writes:** temp dir only; stdout pass/fail lines, exit 1 on failure.
**Called by:** none; run manually. The three check groups run as parallel strands.
**Calls out:** `src.news_pane.pane`, `src.news_pane.log_parser`, `src.pane_error_log` via `importlib`; the strand runner and check helper in `dev/refactoring/`.

---

## State
No persistent state.
