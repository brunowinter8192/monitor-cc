# dev/news_pane/

## Role
Regression checks for the failure paths of `src/news_pane/`. Touch when changing the rag-cli fetch notes, the last-run read or the running state.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python dev/news_pane/fetch_and_running_checks.py`.

## Flow
A fake `rag-cli` on PATH and a temp pane error log drive `_fetch_doc_count`/`_fetch_chunk_count`, `read_last_run_ts` and `_is_running`; each check prints PASS or FAIL.

## Modules

### fetch_and_running_checks.py (115 LOC)

**Purpose:** Proves rag-cli failures return `None` with one note per state change, only `FileNotFoundError` reads as no last run, and the running state comes from the handle alone.
**Reads:** nothing external; fake `rag-cli` and log in a temp dir.
**Writes:** temp dir only; stdout PASS/FAIL lines, exit 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.news_pane.pane`, `src.news_pane.log_parser`, `src.pane_error_log` (via `importlib`).

---

## State
No persistent state.
