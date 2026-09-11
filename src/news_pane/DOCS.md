# src/news_pane/

## Role

Standalone tmux window 5 pane pair that controls and observes the CoinDesk news ingestion
pipeline (lives in the websearch project). LEFT pane NEWS (5.0): shows `searxng_crypto` collection
stats, last-run timestamp, and a clickable `[run pipeline]` button. RIGHT pane NEWS-LOG (5.1):
tails the pipeline's own log file, filters to meaningful stage events, renders top-anchored. No
IPC between the two panes — both reference the same log file on disk. No dependency on
`core/monitor.py` or `active_project_filter`. Touch this package to change the pipeline-control UI
or the log-tail filtering. Do NOT touch it to change the pipeline itself — that lives in the
websearch project.

## Public Interface

- `from src.news_pane.pane import run_news_loop` — entry point for `--mode news` (left pane)
- `from src.news_pane.log_pane import run_news_log_loop` — entry point for `--mode news-log` (right pane)

## Flow

1. **NEWS pane:** `run_news_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop; each tick calls `rag-cli list_documents`/`list_collections --json` for doc/chunk counts and reads `LAST_RUN_FILE` for the last-run timestamp.
2. A click on `[run pipeline]` (blocked while a run is in flight) fires `subprocess.Popen` (fire-and-forget), tracked in `_pipeline_proc`.
3. **NEWS-LOG pane:** `run_news_log_loop()` → 0.5s poll loop (no mouse/keyboard, tmux native scroll active) → `find_log_file()` → `find_current_run_lines()` → `filter_events()` → top-anchored render.

## Modules

### pane.py (296 LOC)

**Purpose:** Left control-pane event loop — collection stats display, SGR mouse/keyboard dispatch, pipeline subprocess launch, running-state indicator, row-1 search bar (highlight-only, no scroll infra). `NEWS_POLL_INTERVAL = 2.0` s; `LOG_RUNNING_RECENT_SECS = 60` (mtime gate for the log-based running-state fallback).
**Reads:** `rag-cli list_documents searxng_crypto` + `rag-cli list_collections --json` (every 2s); `LAST_RUN_FILE` (every 2s); `_pipeline_proc.poll()`; the pipeline log file (via `_is_running_via_log()`).
**Writes:** stdout (full-screen ANSI); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `_pipeline_proc`, `_button_regions`, `_news_search` (query/focused/matches/match_set/current_idx/drag-select fields).
**Called by:** `workflow.py` (`--mode news` route).
**Calls out:** `rag-cli` (subprocess CLI), the websearch project's own pipeline (`WEBSEARCH_ROOT/venv/bin/python -m src.news`, launched via `subprocess.Popen`).

---

### log_pane.py (76 LOC)

**Purpose:** Right log-tail pane. Polls the newest log file every 0.5s, extracts current-run lines, filters to whitelisted events, renders top-anchored (newest visible on overflow). No mouse (tmux native scroll active). `LOG_POLL_INTERVAL = 0.5` s; `MAX_LOG_LINES = 40`.
**Reads:** log file via `find_log_file()` + `find_current_run_lines()` + `filter_events()` (every 0.5s).
**Writes:** stdout (full-screen ANSI); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`).
**Called by:** `workflow.py` (`--mode news-log` route).
**Calls out:** none.

---

### log_parser.py (79 LOC)

**Purpose:** Pure parsing helper + package-level path constants. Provides `WEBSEARCH_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`, run boundary markers, and the whitelist regex list. Functions are side-effect-free beyond the file reads they take as input.
**Reads:** `LOG_DIR/news_coindesk_*.log` (via `find_log_file`); `LAST_RUN_FILE` (via `read_last_run_ts`); log file text (via `find_current_run_lines`).
**Writes:** `/tmp/monitor_cc_error.log` on an unreadable log file in `find_current_run_lines` (via `pane_error_log`).
**Called by:** `pane.py` (constants + `read_last_run_ts`), `log_pane.py` (all parsing functions).
**Calls out:** none.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target)]` | mouse-click handler | `_render_pane` (cleared + rebuilt per tick) |
| `pane.py` | `_pipeline_proc: Popen \| None` | `_is_running()` | `_fire_pipeline()` |
| `pane.py` | `_news_search: search_bar.SearchState` | `.matches` holds 0-based indices into `_render_pane`'s own lines list | mutated by `_poll_news_input`/`_handle_news_mouse` |

## Gotchas

- `log_pane.py` has no search bar — the right log-tail pane's top-anchored, scroll-free rendering is explicitly out of scope for the search-bar rollout.
- `log_parser.py` is the constant anchor for the whole package (`WEBSEARCH_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`) — none of these live in `src/constants.py`.
- `_LOG_LINE_RE`'s `\s+` group before `(.*)` consumes all leading whitespace from the message — whitelist patterns must not include leading spaces (e.g. `\[(OK|FAIL)\]`, not `  \[(OK|FAIL)\]`).
- `_button_regions` for `[run pipeline]` is only registered when `running=False`. While running, a click on that position hits no registered region and is silently ignored.
- Running-state fallback (`_is_running_via_log`) only fires when the log was modified within `LOG_RUNNING_RECENT_SECS` (60s) AND a start marker is present without a subsequent end marker — a stale old log never falsely signals running.
- NEWS-LOG pane uses plain `time.sleep(0.5)` (no raw-stdin setup), so Ctrl+C delivers SIGINT cleanly to `startup.py`'s signal handler.
- `find_current_run_lines()` falls back to all lines when no start marker is found (empty collection / first-ever run).
- The pipeline `Popen` sends stdout+stderr to `DEVNULL` — the pipeline writes its own log file in `LOG_DIR` independently, which is the only channel this pane observes.
