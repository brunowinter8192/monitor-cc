# src/news_pane/

## Role

Standalone tmux Window 5 "news" pane pair that controls and observes the CoinDesk news ingestion pipeline (lives in searxng-cli). LEFT pane NEWS (5.0): shows `searxng_crypto` collection stats (doc count + chunk count), last-run timestamp, clickable `[run pipeline]` button with running indicator. RIGHT pane NEWS-LOG (5.1): tails the pipeline's own log file, filters to meaningful stage events, renders pinned to pane bottom. No IPC between the two panes — both reference the same log file on disk. No dependency on `core/monitor.py` or `active_project_filter`.

## Public Interface

- `from src.news_pane.pane import run_news_loop` — entry point for `--mode news` (left pane)
- `from src.news_pane.log_pane import run_news_log_loop` — entry point for `--mode news-log` (right pane)

## Flow

1. **NEWS pane:** `run_news_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop.
2. Each 2s tick: `_fetch_news_status()` calls `rag-cli list_documents searxng_crypto` (doc count) + `rag-cli list_collections --json` (chunk count) + reads `LAST_RUN_FILE` (last-run timestamp).
3. `_render_pane()` builds display + registers `_button_regions[(start_col, end_col, phys_row) → ('run', 'pipeline')]`. Region only registered when idle — clicks blocked during in-flight run.
4. Mouse click (button=0) → `_is_running()` guard → `_fire_pipeline()` → `subprocess.Popen` fire-and-forget; handle stored in `_pipeline_proc`.
5. `_is_running()`: `_pipeline_proc.poll() is None` OR log fallback (`_is_running_via_log()`).
6. **NEWS-LOG pane:** `run_news_log_loop()` → 0.5s poll loop (no mouse/keyboard, tmux native scroll active).
7. Each tick: `find_log_file()` → `find_current_run_lines()` (lines from last `=== coindesk pipeline started ===`) → `filter_events()` (whitelist + WARNING/ERROR) → `_render_log_pane()` (pins to pane bottom).

## Modules

### pane.py (202 LOC)

**Purpose:** Left control pane event loop. Collection stats display, SGR mouse button click dispatch, subprocess launch, running-state indicator. `NEWS_POLL_INTERVAL = 2.0` s; `LOG_RUNNING_RECENT_SECS = 60`.
**Reads:** `rag-cli list_documents searxng_crypto` + `rag-cli list_collections --json` (every 2s); `LAST_RUN_FILE` (every 2s); `_pipeline_proc.poll()` (every render); log file via `_is_running_via_log()`.
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`).
**Called by:** `workflow.py` (`--mode news` route).
**Calls out:** `click_handler` (keyboard + mouse via `enable_mouse`/`read_mouse_event`), `log_parser` (constants + file helpers), `subprocess.Popen` (pipeline launch).

---

### log_pane.py (80 LOC)

**Purpose:** Right log-tail pane. Polls newest log file every 0.5s; extracts current-run lines; filters to whitelist events; renders pinned to bottom. No mouse (tmux native scroll active). `LOG_POLL_INTERVAL = 0.5` s; `MAX_LOG_LINES = 40`.
**Reads:** log file via `find_log_file()` + `find_current_run_lines()` + `filter_events()` (every 0.5s).
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`).
**Called by:** `workflow.py` (`--mode news-log` route).
**Calls out:** `log_parser` (find_log_file, find_current_run_lines, filter_events, parse_line).

---

### log_parser.py (82 LOC)

**Purpose:** Pure parsing helper + package-level path constants. Provides `SEARXNG_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`, run boundary markers, whitelist regex list. Functions are side-effect-free (no I/O beyond file reads).
**Reads:** `LOG_DIR/news_coindesk_*.log` (via `find_log_file`); `LAST_RUN_FILE` (via `read_last_run_ts`); log file text (via `find_current_run_lines`).
**Writes:** nothing.
**Called by:** `pane.py` (constants + `read_last_run_ts`), `log_pane.py` (all parsing functions).
**Calls out:** nothing beyond stdlib.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target)]` | mouse-click handler in `run_news_loop` | `_render_pane` (cleared + rebuilt per tick) |
| `pane.py` | `_pipeline_proc: Popen \| None` | `_is_running()` | `_fire_pipeline()` |

## Gotchas

- `log_parser.py` is the constant anchor for the package. `SEARXNG_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION` all live there. Both pane.py and log_pane.py import from it — no constants in `src/constants.py`.
- `_LOG_LINE_RE` `\s+` group before `(.*)` consumes ALL leading whitespace from the message — `msg` carries no leading spaces. Whitelist patterns must NOT include leading spaces (e.g. `\[(OK|FAIL)\]`, not `  \[(OK|FAIL)\]`).
- `_button_regions` only registered when `running=False`. While `_is_running()` returns True, any click on the button position hits no registered region → silently ignored. No guard flag needed (unlike gpu_pane `_toggle_state`).
- Running-state fallback (`_is_running_via_log`): log mtime gate of 60s prevents stale old logs from falsely signalling running. Only fires if log was modified within 60s AND start marker present without subsequent end marker.
- NEWS-LOG pane uses plain `time.sleep(0.5)` (no raw-stdin setup) so Ctrl+C delivers SIGINT cleanly to the signal handler in `startup.py`.
- `find_current_run_lines()` falls back to all lines when no start marker found (empty collection / first-ever run).
- Pipeline Popen sends stdout+stderr to DEVNULL. The pipeline writes its own log file in `LOG_DIR` independently.
