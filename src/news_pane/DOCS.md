# src/news_pane/

## Role

Standalone tmux Window 5 "news" pane pair that controls and observes the CoinDesk news ingestion pipeline (lives in websearch). LEFT pane NEWS (5.0): shows `searxng_crypto` collection stats (doc count + chunk count), last-run timestamp, clickable `[run pipeline]` button with running indicator. RIGHT pane NEWS-LOG (5.1): tails the pipeline's own log file, filters to meaningful stage events, renders top-anchored (events grow top-down from the header). No IPC between the two panes — both reference the same log file on disk. No dependency on `core/monitor.py` or `active_project_filter`.

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
7. Each tick: `find_log_file()` → `find_current_run_lines()` (lines from last `=== coindesk pipeline started ===`) → `filter_events()` (whitelist + WARNING/ERROR) → `_render_log_pane()` (top-anchored, newest visible on overflow).

## Modules

### pane.py (354 LOC)

**Purpose:** Left control pane event loop. Collection stats display, SGR mouse button click dispatch, subprocess launch, running-state indicator. `NEWS_POLL_INTERVAL = 2.0` s; `LOG_RUNNING_RECENT_SECS = 60`. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception (this pane previously had none) is caught, logged via `pane_error_log.log_pane_error('news')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) New `[refresh]` header button:** appended to the `CoinDesk News Pipeline` title line (row 1, disjoint from the `[run pipeline]`/`[running…]` button which starts several rows down), registered under `('refresh', 'refresh')`. `_handle_news_mouse` special-cases `action == 'refresh'` (returns `force_refresh_hit=True`) BEFORE the pre-existing `if not _is_running(): _fire_pipeline()` branch — previously that branch fired UNCONDITIONALLY on any matched region regardless of `action`/`target` (there was only ever one button, so this never mattered before). Width-guarded with a real gate — no button text, no region, when it doesn't fit. **(2026-07-30 review fix) Decoration yields to the button, not the reverse:** the `'═' * min(pane_width, 52)` rule used to be computed at FULL length regardless of whether `[refresh]` fit, so the button silently disappeared at pane_width < 86 even though the title text needed only 25 cols — `utils.compute_header_rule_len('  CoinDesk News Pipeline', '[refresh]', 52, pane_width)` now shrinks the rule first (down to a 4-char minimum) to make room for the button. Crossover: button visible from pane_width >= 38 (was 86); title text always renders regardless of width. Verified with a width sweep in `dev/click_ui/p4_gpu_news_button_probe.py` spanning both sides of the crossover, down to well below today's live pane width (107).

**(2026-08-18, rollout sub-milestone 8) Permanent row-1 search bar -- HIGHLIGHT-ONLY, same reduced scope as the gpu pane (`src/gpu_pane/pane.py`, this pane's structural twin): no scroll/viewport infra, so no jump-to-match; `n`/`N` cycles `current_idx` only (which on-screen match gets `SEARCH_CURRENT_BG` vs `SEARCH_MATCH_BG`, and the N/M counter), zero scroll call. `_news_search: search_bar.SearchState`. `_news_search_on_commit` (Enter callback) calls `_render_pane` ONCE without search kwargs, splits/strips/scans exactly like the gpu pane's matcher -- no separate matcher module. `_render_pane` applies highlighting as a single post-loop pass; NO sentinel needed (no per-row background at all, same simple case as gpu/main pane). `_render_pane`'s own `_button_regions` row numbering stays UNSHIFTED -- `_build_news_output` shifts every region by `+_NEWS_SEARCH_BAR_LINES` EXTERNALLY after `_render_pane` returns; `dev/click_ui/p4_gpu_news_button_probe.py` (calls `_render_pane` directly) needed ZERO changes. **`log_pane.py` is explicitly OUT of scope for this milestone** -- excluded per the approved decision, no search bar there.

**(2026-09, news-pane-split milestone) `run_news_loop` (was 111 LOC, hard target) dropped under 50 by applying the exact shape just established in `src/gpu_pane/pane.py` — no new sibling module needed, the file itself already stayed under 400 LOC.** The inline keyboard/mouse drain loop became `_poll_news_input(status) -> (input_changed, force_refresh)` — stays physically in this module (bare-name `read_keypress`/`read_mouse_event` calls, same monkeypatch reason as `gpu_pane`'s `_poll_gpu_input`). The `if button == 0: ...` block (the real-button-event case only — release/cancel handling stays inline in the poll loop) became `_handle_news_mouse(button, col, row) -> (changed, refresh_hit)`. The render + `_button_regions` shift + diff + print tail became `_build_news_output(status, last_output) -> last_output`. `_fire_pipeline`/`_is_running` stayed exactly where they were — `_pipeline_proc` is a scalar rebound via `global` in `_fire_pipeline` and read in `_is_running`, so both must stay physically in this module (same rule as `gpu_pane.pane._toggle_server`'s `PRESET_NAMES` dependency); `dev/pane_search/p8_warnings_gpu_news_parity_test.py` and `dev/click_ui/p4_gpu_news_button_probe.py` also directly assign `mod_news._pipeline_proc = None`, which only works if the module-level name they're patching is the one `_fire_pipeline`/`_is_running` actually read. `_render_pane` (49 LOC) was untouched — already under 50, no byte-identity harness needed since its behavior didn't change.
**Reads:** `rag-cli list_documents searxng_crypto` + `rag-cli list_collections --json` (every 2s); `LAST_RUN_FILE` (every 2s); `_pipeline_proc.poll()` (every render); log file via `_is_running_via_log()`.
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `_news_search` (query/focused/matches/match_set/current_idx/drag-select fields).
**Called by:** `workflow.py` (`--mode news` route).
**Calls out:** `click_handler` (keyboard + mouse via `enable_mouse`/`read_mouse_event`, `copy_to_clipboard`), `log_parser` (constants + file helpers), `pane_error_log` (`log_pane_error`), `utils` (`compute_header_rule_len`, `highlight_query_in_line`), `search_bar` (shared search-bar mechanics), `subprocess.Popen` (pipeline launch).

---

### log_pane.py (83 LOC)

**Purpose:** Right log-tail pane. Polls newest log file every 0.5s; extracts current-run lines; filters to whitelist events; renders top-anchored (events grow top-down from the header, newest visible on overflow). No mouse (tmux native scroll active). `LOG_POLL_INTERVAL = 0.5` s; `MAX_LOG_LINES = 40`. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — the 8th pane loop missed in the initial 2026-07-31 sweep (window 5 has two panes, so this one dying silently leaves pane 5.1 blank rather than killing the whole tmux window, which is why it wasn't caught by the tmux-status-bar symptom that motivated the sweep). An uncaught exception is caught, logged via `pane_error_log.log_pane_error('news_log')`, and the loop continues after `time.sleep(LOG_POLL_INTERVAL)` (this loop has no `wait_for_input`, no keyboard/mouse setup, and — unlike the other 8 — no `finally:` block; none was added, since it never had one and none of its resources need pane-loop-style cleanup).
**Reads:** log file via `find_log_file()` + `find_current_run_lines()` + `filter_events()` (every 0.5s).
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`).
**Called by:** `workflow.py` (`--mode news-log` route).
**Calls out:** `log_parser` (find_log_file, find_current_run_lines, filter_events, parse_line), `pane_error_log` (`log_pane_error`).

---

### log_parser.py (82 LOC)

**Purpose:** Pure parsing helper + package-level path constants. Provides `WEBSEARCH_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`, run boundary markers, whitelist regex list. Functions are side-effect-free (no I/O beyond file reads).
**Reads:** `LOG_DIR/news_coindesk_*.log` (via `find_log_file`); `LAST_RUN_FILE` (via `read_last_run_ts`); log file text (via `find_current_run_lines`).
**Writes:** nothing.
**Called by:** `pane.py` (constants + `read_last_run_ts`), `log_pane.py` (all parsing functions).
**Calls out:** nothing beyond stdlib.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target)]` | mouse-click handler in `run_news_loop` | `_render_pane` (cleared + rebuilt per tick); `('refresh', 'refresh')` value added 2026-07-30 for the header `[refresh]` button, on row 1 — always disjoint from the `('run', 'pipeline')` entry, which starts several rows lower |
| `pane.py` | `_pipeline_proc: Popen \| None` | `_is_running()` | `_fire_pipeline()` |
| `pane.py` | `_news_search: search_bar.SearchState` (2026-08-18) | `.matches` holds 0-based indices into `_render_pane`'s own lines list (no click-interactivity concept for matches) | mutated by `_poll_news_input`/`_handle_news_mouse` (2026-09: extracted from `run_news_loop`'s own former inline dispatch) |

## Gotchas

- **`log_pane.py` has NO search bar** (2026-08-18) -- explicitly excluded from the pane-search rollout per the approved decision. Only `pane.py` (the left control pane) gained one; the right log-tail pane's top-anchored scroll-free rendering was judged out of scope.

- `log_parser.py` is the constant anchor for the package. `WEBSEARCH_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION` all live there. Both pane.py and log_pane.py import from it — no constants in `src/constants.py`.
- `_LOG_LINE_RE` `\s+` group before `(.*)` consumes ALL leading whitespace from the message — `msg` carries no leading spaces. Whitelist patterns must NOT include leading spaces (e.g. `\[(OK|FAIL)\]`, not `  \[(OK|FAIL)\]`).
- `_button_regions` only registered when `running=False`. While `_is_running()` returns True, any click on the button position hits no registered region → silently ignored. No guard flag needed (unlike gpu_pane `_toggle_state`).
- Running-state fallback (`_is_running_via_log`): log mtime gate of 60s prevents stale old logs from falsely signalling running. Only fires if log was modified within 60s AND start marker present without subsequent end marker.
- NEWS-LOG pane uses plain `time.sleep(0.5)` (no raw-stdin setup) so Ctrl+C delivers SIGINT cleanly to the signal handler in `startup.py`.
- `find_current_run_lines()` falls back to all lines when no start marker found (empty collection / first-ever run).
- Pipeline Popen sends stdout+stderr to DEVNULL. The pipeline writes its own log file in `LOG_DIR` independently.
