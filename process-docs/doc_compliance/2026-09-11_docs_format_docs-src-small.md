# Salvage — docs-src-small format cut, 2026-09-11

This file is the salvage of everything cut from the 11 DOCS.md files brought to the DOCS.md
Format in the `docs-src-small` task (`src/DOCS.md` and the DOCS.md of `core/`, `jsonl/`, `input/`,
`format/`, `ram_audit/`, `ccwrap/`, `news_pane/`, `gpu_pane/`, `panes/`, `workers/`), dated
2026-09-11. Every removed sentence is preserved here verbatim, grouped by the DOCS.md path and the
module it came from, before the corresponding DOCS.md was rewritten to the target format. No
triage was applied — this is not a curated summary, it is the raw removed text for RAG recall.

## Salvage from src/DOCS.md

### Entry Points (whole section, removed)

- `workflow.py` → `src.startup`, `src.tmux_launcher`, `src.core.monitor`
- mitmproxy → `src.proxy_addon` (thin shim, loaded via `mitmproxy -s src/proxy_addon.py`)
- tmux panes → `workflow.py --mode <pane>` (each pane is a separate process)

### Directory Map (whole table, removed)

| Subdir | Role | LOC | Modules |
|---|---|---|---|
| `core/` | Session discovery + mode dispatcher (main pane removed 2026-09, see `process-docs/main_pane/`) | 115 | 2 |
| `panes/` | Tmux pane event loops (tokens, warnings) + warnings scan/render/parse helpers + tokens search matcher | 1207 | 5 |
| `format/` | ANSI string rendering (cache tracker) | 327 | 2 |
| `input/` | Keyboard/mouse stdin handling | 154 | 1 |
| `jsonl/` | JSONL parsing (incremental read + cache-turn extraction) | 205 | 2 |
| `workers/` | Workers pane (tmux session discovery + status display) | 878 | 3 |
| `proxy_display/` | Proxy pane TUI (two-level expand, delta rendering, subprocess-parse, copy-button) | 2892 | 8 |
| `proxy/` | mitmproxy addon (payload modification + JSONL logging) | 3074 | 18 |
| `ram_audit/` | SIGUSR1 RAM-dump helper, gated by MONITOR_CC_RAM_AUDIT env | 103 | 1 |
| `menubar/` | macOS status-bar app showing live CC sessions (rumps/AppKit) | 4155 | 25 |
| `gpu_pane/` | GPU server monitor pane (cross-project, reads RAG state) | 734 | 3 |
| `news_pane/` | CoinDesk news pipeline control (left) + live log tail (right) | 501 | 3 |
| `hooks/` | Global CC safety hooks (PreToolUse scripts + hook_setup) | 1674 | 22 |
| `ccwrap/` | Standalone PTY wrapper with diagnostic ANSI logging for CC (Phase 1 diagnostic tool) | 232 | 4 |

### constants.py (Root-Level Files table row, removed)

77 LOC | Timing/size limits (`POLL_INTERVAL`, `INPUT_POLL_INTERVAL`, `WARNINGS_POLL_INTERVAL`, `TMUX_HISTORY_LIMIT`, `EXPANDED_MAX_LINES`, `PROXY_MESSAGES_KEEP_LAST`, `PROXY_REPARSE_INTERVAL_SECONDS`, `WORKER_COL_WIDTH`, `WARNINGS_INITIAL_TAIL_BYTES`), `TOOL_BLOCKLIST`, and the `HOOK_*` cluster (25 CC hook-event-name constants + `HOOK_EVENT_CATEGORIES`) — zero clusters among the timing/size-limit names, `HOOK_*` is the only cluster left in this file. **(2026-09, constants-split milestone)** was 154 LOC with 4 clusters (`PASTEL_*`, `PANE_ERROR_LOG_*`, `MODE_*`, `HOOK_*`) — split by cluster: `PASTEL_*` (+ every other ANSI color/background constant) moved to `colors.py`; `PANE_ERROR_LOG_*` moved into `pane_error_log.py` (the module that already owns that concern); `MODE_*` moved to `core/modes.py` (its sole importer, `core/monitor.py`). `HOOK_*`/`HOOK_EVENT_CATEGORIES` deliberately STAYED — grep-confirmed **zero importers anywhere in `src/`/`dev/`** (every other `HOOK_`-prefixed name in the codebase is an unrelated local `_HOOK_*` constant in a different module, e.g. `menubar/hook_setup.py`'s `_HOOK_EVENTS`); a dedicated module for a cluster nothing imports would be dead code on arrival, and leaving it here is free — it's the only cluster remaining in this file, which satisfies the split rule on its own. Byte-identical values verified via `dev/constants/split_byte_identity.py`.

### colors.py (Root-Level Files table row, removed)

27 LOC | **(2026-09, constants-split milestone, new)** ANSI colors + backgrounds (`RESET`…`SEARCH_CURRENT_BG`, incl. the `PASTEL_*` cluster, `DIM*`, `ZEBRA_*`, `SEARCH_*_BG`, `HOVER_BG`, `LIGHT_RED_BG`, `COLLISION_BG`, `SOFT_RESET`) — split out of `constants.py`. Imported by ≥2 subdirectories (`core`, `format`, `gpu_pane`, `news_pane`, `panes`, `proxy_display`, `workers`) plus root `search_bar.py`/`session_finder.py`/`startup.py`/`utils.py` — stays at root, same shallow-path rationale as `constants.py`/`utils.py`/`pane_error_log.py`. Catppuccin Mocha palette (https://catppuccin.com/palette/), truecolor ANSI `\033[38;2;R;G;Bm` (FG) / `\033[48;2;R;G;Bm` (BG). Semantic mapping: text=Text, title=Mauve, title-soft=Lavender, error=Red, warning=Yellow, success=Green, info=Blue, accent=Sky, accent-warm=Peach, hover-bg=Surface1, zebra-bg=Surface0, error-bg=Red, stripped-bg=custom mustard.

### utils.py (Root-Level Files table row, removed)

166 LOC | Same — `format_timestamp` + `visual_line_count` used everywhere; also `append_copy_symbol` (right-align a ⎘/✓ symbol, width-guarded — shared by `core.monitor_display`, `format.token_format`, `panes.warnings_render`, `workers.worker_format`, and `proxy_display`'s own reference implementation stays independent), `compute_header_rule_len` (shrinking-decoration header layout, shared by `gpu_pane`/`news_pane`), `highlight_query_in_line` (2026-08, browser-find-style inline substring BG highlight, ANSI-safe; `restore_bg` param defaults to `\033[49m` for callers with no per-row background — used directly by `core.monitor_display` since 2026-08-18 (its own identical private copy was deleted, rollout sub-milestone 2) and by `format.token_format` since sub-milestone 4 (passed a `search_bar._BG_RESTORE_SENTINEL` restore_bg, since the tokens pane DOES have a per-row background); `search_bar.py` passes a caller-owned sentinel instead, substituted for the real row background once known, for panes WITH a per-row background), and `wrap_visible` (2026-08-28, thinking-expander milestone — the repo's first word-wrap helper, cell-aware via `_cell_width` like `truncate_visible`, NOT character-count-based; breaks on spaces, hard-splits a single word wider than the target width; currently used only by `proxy_display/render_messages.py`'s thinking-block content wrapping)

### search_bar.py (Root-Level Files table row, removed)

147 LOC | Shared search-bar mechanics (2026-08-18, sub-milestone 1 of the pane-search rollout — extracted from `proxy_display/pane.py`, the reference implementation) — `SearchState`, `render_search_bar`, `col_to_query_index`, `handle_search_input`/`_cancel`, the drag-select mouse handlers, and the `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` pair. Imported by `proxy_display` (sub-milestone 1's `pane.py` AND sub-milestone 3's `worker_proxy_pane.py`, 2026-08-18 — the latter imports only `SearchState`/`render_search_bar`/the input+drag handlers, not `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` directly, since that sentinel machinery already lives in the SHARED `format.py`/`render_turn.py` render pipeline both proxy panes call through — worker_proxy_pane's own zebra/hover rows get the same sentinel-based highlight preservation automatically, no separate import needed), `core` (sub-milestone 2, 2026-08-18 — the main pane's `_main_search`), `panes`/`format` (sub-milestone 4, 2026-08-18 — the tokens pane's `_tokens_search`; `format/token_format.py` imports `_BG_RESTORE_SENTINEL` directly to embed search highlights at construction time, `panes/token_pane.py` imports `resolve_bg_restore` to resolve them in its own hand-rolled row loop — same `ZEBRA_BG_A == ''` trap the proxy pane hit, fixed the same way), `workers` (sub-milestone 5, 2026-08-18 — the workers pane's `_worker_search`; same `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` split between `worker_format.py` (embed) and `worker_pane.py` (resolve, own hand-rolled loop) as the tokens pane — third occurrence of the identical sentinel fix), `panes.warnings_pane`/`warnings_render` (sub-milestones 6-8, 2026-08-18, bundled — the warnings pane's `_warnings_search`; fourth sentinel occurrence, `ZEBRA_BG_A==''` still applied even though this pane's PRE-EXISTING `DIM_YELLOW_BG` detection was already substring-based, verified before assuming), and `gpu_pane`/`news_pane` (sub-milestones 7-8, 2026-08-18 — `_gpu_search`/`_news_search`; HIGHLIGHT-ONLY, no jump-to-match, no sentinel needed at all — neither pane has any per-row background/zebra/hover loop, so `utils.highlight_query_in_line`'s default `restore_bg` is directly correct, same simple case as the main pane; `search_bar.py`'s drag-select/editor-deletion functions called directly at each pane's own INLINE mouse/key dispatch, since neither pane factors dispatch into a standalone handler function) — same shallow-path rationale as `constants.py`/`utils.py`. Rollout complete as of sub-milestone 8 — all 8 panes now share this module (`news_pane/log_pane.py` explicitly excluded per decision). See `proxy_display/DOCS.md` and `core/DOCS.md` for each retrofit and `process-docs/pane_search/` for the rollout plan.

### pane_error_log.py (Root-Level Files table row, removed)

30 LOC | `log_pane_error(pane_name)` — shared exception-safe sink all 8 pane `run_*_loop()` functions call from their `except Exception:` guard (2026-07-31); imported by every pane module the same shallow-path way as `constants.py`, so it belongs at the same level. **(2026-09, constants-split milestone)** now defines `PANE_ERROR_LOG_PATH`/`PANE_ERROR_LOG_MAX_BYTES`/`PANE_ERROR_LOG_KEEP_BYTES` itself (moved from `constants.py`'s `PANE_ERROR_LOG_*` cluster — this module already owned the concern) instead of importing them.

### session_finder.py (Root-Level Files table row, removed)

77 LOC | Single module, no subpackage warranted

### startup.py (Root-Level Files table row, removed)

43 LOC | Single module; only called by `workflow.py`

### tmux_launcher.py (Root-Level Files table row, removed)

245 LOC | Single module; only called by `workflow.py` (mode `all` → `launch_split_screen`; mode `restart-panes` → `restart_panes`, the Ctrl+R self-heal handler). **(2026-09, remaining-thresholds milestone)** `launch_split_screen`/`restart_panes` were both over the 50-LOC function threshold — `launch_split_screen` now reuses `_build_mode_commands` for its 8 mode-command strings (was duplicated inline, byte-identical construction) and delegates the window/split sequence to `_create_windows(session_name, cmds)`; `restart_panes` gained `_list_pane_modes(session_name, win_idx)` (the thrice-repeated list-panes+parse), `_create_missing_window(...)`, `_fill_missing_panes(...)`, `_respawn_all_panes(session_name)`. Byte-identical `subprocess.run` argv sequences verified via `dev/tmux_launcher/argv_byte_identity.py`. 6-Window Layout: Window 0 "tokens" (fullscreen); 1 "proxy" (fullscreen); 2 "workers" (left 34%) + worker-proxy (right 66%); 3 "debug" = warnings (fullscreen); 4 "gpu" (fullscreen); 5 "news" (left 50%) + news-log (right 50%).

### monitor_janitor.py (Root-Level Files table row, removed)

69 LOC | `sweep_workflow()` — kills every `monitor_cc_*` tmux session older than 24h (registry-free `tmux list-sessions` enumeration, same lesson as the worker-cli janitor), logs one line per session (name, age, KILLED/SPARED) to `<checkout>/src/logs/monitor_sweep.log`, where `<checkout>` is `$MONITOR_CC_ROOT` if set, else the directory two levels above `monitor_janitor.py`'s own `__file__` — so a manual run from a `.claude/worktrees/<name>/` checkout writes into THAT worktree's `src/logs/`, not the main checkout's, unless `MONITOR_CC_ROOT` is set. No main-checkout fallback like `dual_log_cli.discovery.resolve_dual_log_dir` — this path is a write target that must follow whichever checkout's code produced the entry, not a read source to prefer aggregating in one place. Invoked as `python3 -m src.monitor_janitor` from project root — from `claude_proxy_start.sh` (detached, every main-session start; bash `cd`'s into `$MONITOR_CC_ROOT` first, so `__file__` resolves correctly without an explicit env var) and, 2026-09, from `src/menubar/monitor_sweep_scheduler.py`'s daily tick-gated call (`sweep_workflow()` imported directly, not `-m`; sets `$MONITOR_CC_ROOT` explicitly first, since a frozen py2app bundle's own `__file__` resolves inside the bundle copy). **This module's own dedicated LaunchAgent (`com.brunowinter.monitor-cc-sweep.plist` + `setup_monitor_sweep.py`) was removed 2026-09** — a bare launchd-spawned `/usr/bin/python3` has no TCC Full Disk Access grant for a checkout under `~/Documents`, and that block cannot be worked around by any plist or code change (see `process-docs/monitor_lifecycle/`); the daily run moved to the already-launchd-and-TCC-granted menubar app's own tick instead. Never uses `pkill -f` (see `process-docs/pipeline/` `pkill -f` incident) — kills by exact tmux session name only, which tears down all nine panes (verified in `dev/monitor_lifecycle/`).

### proxy_addon.py (Root-Level Files table row, removed)

27 LOC | Thin shim — `claude_proxy_start.sh` copies it to `src/logs/.proxy_addon_live_<id>.py` for per-session isolation. Shim has sys.path logic that finds `src/proxy/` from both root and live-copy locations. Move would break live-copy pattern.

### claude_proxy_start.sh (Root-Level Files table row, removed)

436 LOC | Shell script — launches mitmproxy + Claude Code with proxy env; version-aware purge (Phase 0: hash proxy source, delete stale >60min logs on change) + count-30 quartet-aligned dual-log rotation; per-project marker (src/logs + /tmp) with PID+identity liveness guard + 10s heartbeat reclaim; model precedence (highest first): explicit `--model` (anywhere in the args) > `--fable`/`--opus` shortcut flags (2026-08-06, map to `--model claude-fable-5`/`claude-opus-5`, last one wins if both given) > `main` from `~/.claude/shared-rules/model_selection.json` (2026-08, model-selector milestone 3 — the menubar's Models tab writes this file; read via `jq`, `command -v`-guarded; a missing/unreadable/malformed file or missing/empty key falls through silently) > nothing injected, byte-identical to no-flag behavior; fires a fully-detached `worker-cli janitor` (2026-08-19, `command -v`-guarded, `nohup ... & disown`) before arg-parsing so every main-session start also triggers the iterative-dev stale-tmux-worker sweep — see `iterative-dev` repo's `bin/worker-cli`, unrelated to this script's own `_janitor_*` functions (proxy live-copy/log rotation, pre-existing separate concern, same name coincidental); also fires a fully-detached `python3 -m src.monitor_janitor` (2026-09, `cd "$MONITOR_CC_ROOT"` first so the module path resolves regardless of caller CWD) triggering the monitor-session sweep (`monitor_janitor.py`) on the same every-session-start cadence

### Flow (Main Session) (whole section, removed)

1. `workflow.py` → `run_monitor(project_filter, mode="all")` → `tmux_launcher.launch_split_screen()` spawns 8 panes each running `workflow.py --mode <X>`. **(2026-09) Window 0 is the tokens pane at full width** — the main pane was removed entirely, see `process-docs/main_pane/`.
2. Each pane runs its own event loop (e.g. `run_tokens_loop()`): poll data source → handle mouse/keyboard → render full screen. `core/monitor.py::run_monitor` only discovers sessions and dispatches to the matching loop by `--mode`; it does not run a loop of its own anymore.
3. mitmproxy (started by `claude_proxy_start.sh`) intercepts API traffic, strips/modifies payloads, logs to `src/logs/api_requests_<id>.jsonl`.
4. Panes that need proxy data (proxy_display, warnings) tail that JSONL file independently.

### Gotchas (whole section, removed)

- `KILL_LINE_CHAR = '\x15'` (Ctrl-U) is a HYPOTHESIS from 2026-08-18, not live-confirmed: Cmd+Backspace is normally consumed by the terminal app; Ghostty most likely maps it to 0x15 before it reaches the pane. It is one named constant so a rebind after live testing is a one-line change.
- `restart_panes` known limitation: when several panes in one window are missing at once, the split percentage is applied against whichever pane survived, not the original source, so proportions may differ from the initial launch; the single-missing-pane case always restores the correct size.

### Subdir DOCS (whole section, removed)

- [core/DOCS.md](core/DOCS.md) — session discovery, mode dispatch
- [panes/DOCS.md](panes/DOCS.md) — token, warnings pane loops
- [format/DOCS.md](format/DOCS.md) — strip_marker, token_format
- [input/DOCS.md](input/DOCS.md) — click_handler
- [jsonl/DOCS.md](jsonl/DOCS.md) — jsonl_parser, jsonl_cache_turns
- [workers/DOCS.md](workers/DOCS.md) — worker_pane, worker_format, worker_tmux
- [proxy_display/DOCS.md](proxy_display/DOCS.md) — proxy pane TUI (8 modules)
- [proxy/DOCS.md](proxy/DOCS.md) — mitmproxy addon (18 modules)
- [ram_audit/DOCS.md](ram_audit/DOCS.md) — SIGUSR1 RAM-dump helper (env-gated tracemalloc)
- [menubar/DOCS.md](menubar/DOCS.md) — macOS menubar app (rumps, session discovery, background-task badge)
- [gpu_pane/DOCS.md](gpu_pane/DOCS.md) — GPU monitor pane (status, errors, toggle)
- [news_pane/DOCS.md](news_pane/DOCS.md) — CoinDesk news pipeline control pane + live log pane
- [hooks/DOCS.md](hooks/DOCS.md) — Global CC PreToolUse safety hooks (block scripts + hook_setup)
- [ccwrap/DOCS.md](ccwrap/DOCS.md) — PTY wrapper with diagnostic ANSI logging (Phase 1 diagnostic tool)

## Salvage from src/core/DOCS.md

### Role (removed prose)

**(2026-09) The main pane and its whole rendering/classification pipeline were removed** — window 0 is now the tokens pane at full width, see `process-docs/main_pane/`. `monitor.py` is what's left: it discovers JSONL session files, tracks which ones are live, and dispatches each `--mode` to its own pane package (`workers`, `panes.token_pane`, `panes.warnings_pane`, `proxy_display`).

### Public Interface (removed prose)

**(2026-09) `monitor_display.py` and `monitor_session.py` removed entirely** — both existed only to serve the main pane's tool-call classification/rendering pipeline (`process_session_file`, `display_tool_call`, `display_warning`, `print_session_status`, `render_main_buffer`, `run_main_loop`, and everything only they used). Their only other caller was the warnings pane's `monitor_sessions()` call, which never needed the classification output — it always drew `tool_errors` from the proxy's `_errors` dual-logs, never from this pipeline's `display_warning` (which fed the main pane's own buffer, now gone). `monitor_sessions()` survives as pure session-file bookkeeping.

### modes.py (removed heading annotation and Purpose text)

Heading was: `### modes.py (8 LOC, new 2026-09, constants-split milestone)`

Purpose text: `MODE_*` constants (`MODE_ALL`/`MODE_WARNINGS`/`MODE_TOKENS`/`MODE_WORKERS`/`MODE_PROXY`/`MODE_WORKER_PROXY`) — split out of `src/constants.py`'s `MODE_*` cluster. `monitor.py` is this cluster's sole importer anywhere in `src/`/`dev/`, so it moved into this package rather than staying at root.

### monitor.py (removed Purpose detail and Calls out detail)

Purpose text: `get_main_session_files`/`_get_newest_main_session`/`_get_session_start_ts` resolve the current project's newest non-agent session JSONL — read by `proxy_display/pane.py`, `panes/token_pane.py`, `proxy_display/worker_proxy_pane.py`. `monitor_sessions()`/`update_session_tracking()` maintain `file_positions` (new/removed session files only) — read by the warnings pane on startup and every poll tick; no other pane consumes this state. `get_file_end_position`/`get_initial_position` (moved here from the now-deleted `monitor_session.py`) compute where a tracked file's byte offset starts.

Calls out text: `session_finder`, `jsonl` (`parse_jsonl_lines`, `read_new_lines`, for `_get_session_start_ts`); `.modes` (`MODE_*`, 2026-09 constants-split milestone — re-pointed from `..constants`); lazy: `workers`, `panes`, `proxy_display` (mode-dispatch imports).

### Gotchas (removed items)

- `_get_session_start_ts()` reads the newest main session JSONL and subtracts 10s (comment says 60s — pre-existing discrepancy, not touched by the 2026-09 main-pane removal) as the cutoff. Changing this affects `proxy_display`'s historical-replay window.
- `monitor_sessions()` is a bookkeeping no-op as far as any pane's *displayed content* goes — it only keeps `file_positions` in sync with which session files currently exist. The warnings pane calls it out of habit from when it fed a shared tool-call pipeline; nothing currently reads the result. Kept because `monitor_sessions` is documented pane-facing API (see `panes/DOCS.md`), not because anything depends on its side effect today.
- The 24h log janitor sweep (`log_janitor.cleanup_old_jsonl` over `sweep_eligible_specs`) used to run from this package's `run_main_loop`. It now runs from `panes/token_pane.py::run_tokens_loop` instead — the tokens pane is the always-active, main-checkout-resident pane that replaces the main pane's role as the janitor's host (see `process-docs/logging/log_janitor.md` and `process-docs/main_pane/`).

## Salvage from src/jsonl/DOCS.md

### Role (removed prose)

**(2026-09) The tool_use/tool_result correlation + classification path removed** — `extract_tool_calls`, `create_tool_use_entry`, `update_request_numbers`, `parse_new_tool_calls`/`parse_new_tool_calls_isolated` (and its subprocess worker), `is_tool_result`, `get_progress_content`, `extract_spawned_agent_id`, `extract_result_content`, `filter_excluded_tools`, `sort_by_timestamp`, `build_malformed_warnings` all had exactly one real caller, `core/monitor_session.py`, which was deleted along with the main pane it fed (window 0 is now the tokens pane at full width — see `process-docs/main_pane/`). `jsonl_extractors.py` (user media/prompts/thinking/skills/usage/system-message extraction) lost its only caller the same way and was deleted entirely.

### jsonl_parser.py (removed Called by detail)

`panes/token_pane.py`, `workers/worker_format.py` (`read_new_lines`, `parse_jsonl_lines`, `get_current_position`, `get_message_content`, `is_tool_use` — all lower-level functions; there is no higher-level "parse tool calls" entry point anymore, see Role above).

### jsonl_cache_turns.py (removed heading annotation, Purpose detail, private-helpers line)

Purpose text (removed continuation): **(2026-09, tokens-data-render-helpers milestone):** `extract_cache_turns` was 65 LOC — split into `_start_turn_from_user(message, current_turn, turns) -> Optional[dict]` (the external-user-message branch: starts a new turn for a skill-command or a plain prompt, or returns `current_turn` unchanged for a tool-result/empty/skill-preamble/duplicate-timestamp message — every early-exit path in the original just fell through to `continue` without touching `current_turn`, so the helper's "unchanged" return reproduces that exactly) and `_absorb_assistant_call(message, current_turn) -> None` (the assistant branch: dedup-merge into the last call or append a new one — mutates `current_turn` in place, same as before the split). `extract_cache_turns` itself is now a 2-branch dispatch loop calling these, byte-identical (`dev/panes/render_byte_identity.py`'s `build_cache_turns` incremental-chunk check, hash unchanged before/after).

Also mentions each `api_call` dict's 6 usage extras (`cache_creation_ttl`, `server_tool_use`, `service_tier`, `speed`, `inference_geo`, `iterations`) inline in the Purpose paragraph, and a trailing line: `Private helpers (same module): _parse_user_message_text, _extract_content_blocks, _build_api_call, _merge_duplicate_call, _start_turn_from_user, _absorb_assistant_call.`

## Salvage from src/input/DOCS.md

### click_handler.py (removed Purpose detail, sentinel/UTF-8 fix narrative)

Purpose text (removed continuation): Also provides `resolve_parent_key(line_map, hover_row)` (walk hover_row down to nearest mapped key), `copy_to_clipboard(text)` (pipe to pbcopy) used by every pane's `y`-hotkey handler, and `wait_for_input(timeout)` (block on `select.select` for stdin or timeout, fallback to `time.sleep` if stdin not raw) — used in every pane's main loop instead of fixed `time.sleep` so input wakes the loop immediately.

**`read_mouse_event` return shape (2026-05-22 sentinel addition, commit `bf1f158`):** parses `\033[<b;col;rowM` (press, terminator `M`) returning `(button, col, row)`; parses `\033[<b;col;rowm` (release, terminator `m`) returning the sentinel `(-1, -1, -1)`; returns `None` for non-mouse sequences (bare-ESC keypress, malformed input). Callers that only care about press events check `event is not None and event[0] != -1`; callers that need release detection check for the sentinel. The sentinel resolves the search-bar focus-cancel bug where bare-ESC handling fired on every mouse release because both produced `None` return.

**`read_keypress` — multi-byte UTF-8 decoding (2026-08-18 fix).** Previously read exactly 1 byte and decoded it alone (`errors='replace'`) — a multi-byte UTF-8 character (em-dash = 3 bytes, ä/ö/ü = 2 bytes, most emoji = 4 bytes) arrived as N separate `os.read(fd, 1)` calls, each individually invalid UTF-8, each replaced with U+FFFD (`'�'`) — reported live as an em-dash typed into the proxy search bar rendering as three `���`. Fixed: reads the lead byte first (unchanged non-blocking-select fast path for "nothing pending" → `None`), classifies it via `_utf8_continuation_count(lead_byte)` (UTF-8 bit-pattern: `0xxxxxxx`=0 continuation bytes, `110xxxxx`=1, `1110xxxx`=2, `11110xxx`=3), then reads that many more bytes — each gated by the SAME `select.select(..., 0.005)` timeout `read_mouse_event` already uses for its own byte-wise ESC-sequence continuation reads (reused for consistency, not reinvented) — and decodes the whole sequence together. Plain ASCII (0 continuation bytes) takes the exact same code path as before, byte-for-byte — zero added latency for the overwhelming majority of keypresses. A read error now propagates to the caller's own outer `try/except Exception: log_pane_error(...)` (every pane loop wraps its drain loop in one) instead of being silently swallowed inside `read_keypress` itself. Verified against both `input.click_handler.read_keypress` directly (via a real `os.pipe()` fd, not a mock) and the full search-input path in both `proxy_display/pane.py` and `core/monitor_display.py` (confirming the shared reader fix heals BOTH search bars) — `dev/pane_search/p2_search_feature_regression_test.py`.

Trailing line: `New private helper (same module): _utf8_continuation_count.`

## Salvage from src/format/DOCS.md

### Role/Public Interface (removed prose)

**(2026-09) `formatter.py` and `formatter_events.py` removed entirely, main pane deleted** — `format_tool_call`/`format_request`/`format_response`/`combine_request_response`/`format_todo_list`/`format_parameters`/`format_task_parameters`/`format_output`/`format_error_output`/`format_value`/`get_status_icon`/`get_status_color` all had exactly one caller, `core/monitor_display.py`, which was deleted along with the main pane it rendered (window 0 is now the tokens pane at full width — see `process-docs/main_pane/`). `shorten_tool_name` had a second real caller (`token_format.py` itself) and moved there instead of dying with the rest of the module. `formatter_events.py` was already removed in an earlier pass (2026-09, tool-calls-only redesign) once `core/monitor_session.py` stopped displaying non-tool-call event types.

### strip_marker.py (removed Purpose detail)

`get_stripped_data`, `build_tool_result_strip_lookup`, and `build_tool_id_strip_lookup` deleted in Stage 3 (main-pane strip overlay removed).

### token_format.py (removed Purpose narrative, milestone paragraphs, private-helpers line)

Purpose narrative (removed): Return arity UNCHANGED since 2026-08-18 (see below). `format_cache_tracker` accepts an optional `response_rid_map: dict` (keyed by `request_id`); when a call's `request_id` matches, renders (1) usage-extras lines above the content-blocks loop (5m/1h TTL split, web_search/web_fetch if non-zero, tier/speed/geo, iteration count) and (2) rate-limit header lines (`rl: 5h:X%→HH:MM  7d:X%→…`; status/overage in YELLOW when non-nominal). Graceful when map absent or request_id not matched. **(2026-07-30) Optional `copy_feedback: Optional[dict] = None`** (keyed by `(turn_idx,call_idx)`, same as `line_keys`) — when given, appends a `⎘`/`✓` symbol to the call-summary line via `utils.append_copy_symbol`; `None` (the default, used by every pre-existing caller) skips the branch entirely, byte-identical to before.

**(2026-09, tokens-data-render-helpers milestone) two functions over 50 LOC split into line-group/per-unit helpers, byte-identical behavior (`dev/panes/render_byte_identity.py`'s new `format_cache_tracker` case + the pre-existing `dev/workers/format_byte_identity.py` hash, both unchanged before/after):**
- **`_render_expanded_call_lines`** (was 87 LOC) → 3 line-group helpers, each returning `(lines, keys)`: `_render_usage_extras_lines(call)` (TTL split / web_search-fetch / tier-speed-geo / iteration-count lines), `_render_rate_limit_lines(call, response_rid_map)` (the `rl:` line + YELLOW warn line — empty when the call's `request_id` has no `response_rid_map` entry), `_render_content_block_lines(call)` (the tool_use/thinking/text loop). `_render_expanded_call_lines` itself is now a 3-call sequence extending `lines`/`keys` from each group.
- **`format_cache_tracker`** (was 74 LOC) → `_render_call_line(...) -> (call_line, key, marker)` (the per-call summary-line build — symbol/`_format_cache_call`/search-marker-wrap/copy-symbol; `marker` is `None` unless this call is a search match, telling the caller whether/how to highlight the call's expanded detail lines) and `_render_turn_lines(...) -> int` (renders one turn's header + all its call lines + trailing blank line, appending directly into the caller's `all_lines`/`line_keys` rather than returning a sub-list — the in-place-mutation contract `nav_out` already used, needed here too since `nav_out`'s indices are absolute positions in the whole-render line list; returns the updated `request_num`, a running counter across turns). `format_cache_tracker`'s per-turn loop is now `request_num = _render_turn_lines(...)`; the pre-existing dead, never-referenced `prompt_max` computation at the top is untouched (out of this milestone's scope).

**(2026-08-18, rollout sub-milestone 4) Search-highlight embedding — 4 new optional params, ZERO return-arity change.** `search_match_set: Optional[set]`, `search_current_key`, `search_query: str = ''`, `nav_out: Optional[dict] = None`. A match key is either `(turn_idx, call_idx)` [found in that call's own header or force-expanded detail content] or `('turn', turn_idx)` [found in the turn's own prompt/timestamp line]. BOTH get an UNCONDITIONAL whole-line "container mark" (`f"{marker}{line}{search_bar._BG_RESTORE_SENTINEL}"`, `marker` = `SEARCH_CURRENT_BG` or `SEARCH_MATCH_BG`) — not a literal-substring-only wrap, since the actual matching text may be buried in unrendered (collapsed) detail; mirrors `proxy_display`'s REQ-header "text extent" marking. An EXPANDED matching call additionally gets its specific matching detail line(s) browser-find substring-highlighted via `utils.highlight_query_in_line(line, search_query, marker, _BG_RESTORE_SENTINEL)` — header stays marked too (uniform, keeps orientation when scrolling). `('turn', idx)` keys are deliberately NEVER added to `line_keys` — turn headers stay non-interactive for clicks exactly as before this milestone; `nav_out`, when given, is populated (`.clear()`-then-rewritten in place, same contract as `proxy_display.format`'s `copy_rows_out`) with `{key: absolute_line_idx, ..., 'total_lines': N}` for the caller's OWN jump-to-match scroll math — deliberately a SEPARATE out-param from `line_keys`/return value, so `workers/worker_format.py`'s reuse of this function (which assumes every non-None key is a plain 2-int-tuple, `(name, ck[0], ck[1])`) is completely unaffected. All 4 new params default to no-op values — verified byte-identical against all 4 real callers (`token_pane.py`, `workers/worker_format.py`, `dev/click_ui/p2_copy_click_probe.py`, `dev/display/A_format_cache_tracker_proof.py`) via a frozen-turns old-vs-new comparison held constant in one process (the live `A_format_cache_tracker_proof.py` harness reads directly from `~/.claude/projects/.../*.jsonl` — the top-10-most-recently-modified REAL session files — which were actively growing during this milestone's own session, producing a false-positive mismatch on a naive capture-then-verify-later run; see `process-docs/pane_search/` for the full writeup). Two helpers extracted for this: `_format_turn_header_line(turn_idx, turn, pane_width)` (prompt-truncation/timestamp/think_str construction, now shared by the real render loop AND `panes/token_search.py`'s matcher so they can never disagree) and `_call_thinking_meta(call)` (has_thinking/sig_chars extraction, same rationale).

Trailing line: `Private helpers (same module): _fmt_rl_reset_time, _render_expanded_call_lines (+ _render_usage_extras_lines, _render_rate_limit_lines, _render_content_block_lines), _compute_cache_viewport, _call_thinking_meta, _format_turn_header_line, _render_call_line, _render_turn_lines.`

### Gotchas (removed item)

**(2026-09)** `shorten_tool_name` used to live in the now-deleted `formatter.py` (`from .formatter import shorten_tool_name`) — moved into `token_format.py` itself since this was its only remaining caller once the main pane (`formatter.py`'s other consumer) was removed. No import needed anymore; it's a plain module-level function here.

## Salvage from src/ram_audit/DOCS.md

### instrument.py (removed milestone paragraph)

**(2026-09, remaining-thresholds milestone):** `register_ram_dump`/`_handle_ram_dump` were 84/60 LOC — split into module-level report-section helpers, each returning a line list (or, for RSS, a single line): `_rss_line()`, `_gc_top_lines()`, `_tracemalloc_lines()`, `_module_state_lines(provider)`, plus `_resolve_dump_path(pane_name, ts)` (dump-dir/`MONITOR_CC_ROOT` resolution, needed in addition to the 4 report-section helpers to get `register_ram_dump` itself under 50 LOC). `_handle_ram_dump` stays a closure (still needs `pane_name`/`module_state_provider` from its enclosing scope) but shrank to header-line assembly + 4 helper calls + write. Byte-identical dump structure verified via `dev/ram_audit/dump_byte_identity.py` (real memory-state rows — gc counts, tracemalloc stats — are inherently non-deterministic across runs and normalized out by that harness; the report's fixed structure and the fully-deterministic module-state section are what's actually hashed).

### Usage (whole section, removed)

Trigger a single pane:
```bash
kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)
```

Trigger all running panes at once:
```bash
dev/ram_audit/dump_all.sh
```

## Salvage from src/ccwrap/DOCS.md

### __init__.py (removed Modules entry, trivial marker file)

**Purpose:** Package marker.
**Reads:** nothing. **Writes:** nothing.
**Called by:** Python import system.
**Calls out:** nothing.

### Usage (whole section, removed)

```bash
# Wrap real CC session (default project = Monitor_CC):
python3 -m src.ccwrap

# With explicit project:
python3 -m src.ccwrap --project /path/to/my/project

# Smoke test (quick-exit command, write logs to src/logs/ccwrap/):
python3 -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from src.ccwrap.wrapper import run
run(['bash', '-c', r'echo hi; printf \"\033[2J\033[H\"; echo done'], Path('src/logs/ccwrap'))
"
```

Logs land in `_LOG_DIR` (`logs/ccwrap/` under project root, gitignored).

## Salvage from src/news_pane/DOCS.md

### pane.py (removed milestone paragraphs)

`NEWS_POLL_INTERVAL = 2.0` s; `LOG_RUNNING_RECENT_SECS = 60`. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception (this pane previously had none) is caught, logged via `pane_error_log.log_pane_error('news')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) New `[refresh]` header button:** appended to the `CoinDesk News Pipeline` title line (row 1, disjoint from the `[run pipeline]`/`[running…]` button which starts several rows down), registered under `('refresh', 'refresh')`. `_handle_news_mouse` special-cases `action == 'refresh'` (returns `force_refresh_hit=True`) BEFORE the pre-existing `if not _is_running(): _fire_pipeline()` branch — previously that branch fired UNCONDITIONALLY on any matched region regardless of `action`/`target` (there was only ever one button, so this never mattered before). Width-guarded with a real gate — no button text, no region, when it doesn't fit. **(2026-07-30 review fix) Decoration yields to the button, not the reverse:** the `'═' * min(pane_width, 52)` rule used to be computed at FULL length regardless of whether `[refresh]` fit, so the button silently disappeared at pane_width < 86 even though the title text needed only 25 cols — `utils.compute_header_rule_len('  CoinDesk News Pipeline', '[refresh]', 52, pane_width)` now shrinks the rule first (down to a 4-char minimum) to make room for the button. Crossover: button visible from pane_width >= 38 (was 86); title text always renders regardless of width. Verified with a width sweep in `dev/click_ui/p4_gpu_news_button_probe.py` spanning both sides of the crossover, down to well below today's live pane width (107).

**(2026-08-18, rollout sub-milestone 8) Permanent row-1 search bar -- HIGHLIGHT-ONLY, same reduced scope as the gpu pane (`src/gpu_pane/pane.py`, this pane's structural twin): no scroll/viewport infra, so no jump-to-match; `n`/`N` cycles `current_idx` only (which on-screen match gets `SEARCH_CURRENT_BG` vs `SEARCH_MATCH_BG`, and the N/M counter), zero scroll call. `_news_search: search_bar.SearchState`. `_news_search_on_commit` (Enter callback) calls `_render_pane` ONCE without search kwargs, splits/strips/scans exactly like the gpu pane's matcher -- no separate matcher module. `_render_pane` applies highlighting as a single post-loop pass; NO sentinel needed (no per-row background at all, same simple case as gpu/main pane). `_render_pane`'s own `_button_regions` row numbering stays UNSHIFTED -- `_build_news_output` shifts every region by `+_NEWS_SEARCH_BAR_LINES` EXTERNALLY after `_render_pane` returns; `dev/click_ui/p4_gpu_news_button_probe.py` (calls `_render_pane` directly) needed ZERO changes. **`log_pane.py` is explicitly OUT of scope for this milestone** -- excluded per the approved decision, no search bar there.

**(2026-09, news-pane-split milestone) `run_news_loop` (was 111 LOC, hard target) dropped under 50 by applying the exact shape just established in `src/gpu_pane/pane.py` — no new sibling module needed, the file itself already stayed under 400 LOC.** The inline keyboard/mouse drain loop became `_poll_news_input(status) -> (input_changed, force_refresh)` — stays physically in this module (bare-name `read_keypress`/`read_mouse_event` calls, same monkeypatch reason as `gpu_pane`'s `_poll_gpu_input`). The `if button == 0: ...` block (the real-button-event case only — release/cancel handling stays inline in the poll loop) became `_handle_news_mouse(button, col, row) -> (changed, refresh_hit)`. The render + `_button_regions` shift + diff + print tail became `_build_news_output(status, last_output) -> last_output`. `_fire_pipeline`/`_is_running` stayed exactly where they were — `_pipeline_proc` is a scalar rebound via `global` in `_fire_pipeline` and read in `_is_running`, so both must stay physically in this module (same rule as `gpu_pane.pane._toggle_server`'s `PRESET_NAMES` dependency); `dev/pane_search/p8_warnings_gpu_news_parity_test.py` and `dev/click_ui/p4_gpu_news_button_probe.py` also directly assign `mod_news._pipeline_proc = None`, which only works if the module-level name they're patching is the one `_fire_pipeline`/`_is_running` actually read. `_render_pane` (49 LOC) was untouched — already under 50, no byte-identity harness needed since its behavior didn't change.

### State table (removed history annotations)

`('refresh', 'refresh')` value added 2026-07-30 for the header `[refresh]` button, on row 1 — always disjoint from the `('run', 'pipeline')` entry, which starts several rows lower.
`_news_search: search_bar.SearchState` (2026-08-18) — mutated by `_poll_news_input`/`_handle_news_mouse` (2026-09: extracted from `run_news_loop`'s own former inline dispatch).

### Gotchas (removed item)

- **`log_pane.py` has NO search bar** (2026-08-18) -- explicitly excluded from the pane-search rollout per the approved decision. Only `pane.py` (the left control pane) gained one; the right log-tail pane's top-anchored scroll-free rendering was judged out of scope.

## Salvage from src/gpu_pane/DOCS.md

### pane.py (removed milestone paragraphs)

**(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception (this pane previously had none, and could die silently) is caught, logged via `pane_error_log.log_pane_error('gpu')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Digit keys need no new button:** the per-preset row's ALREADY-registered `_button_regions` entry (`action` = `('stop' if healthy else 'restart') if running else 'start'`, `target` = preset name) computes the IDENTICAL action and fires the IDENTICAL `rag-cli server <action> <name>` subprocess call as `_toggle_server(idx, presets)` (what the digit key calls) — `presets = [_status_for_preset(n, ...) for n in PRESET_NAMES]` guarantees `presets[idx]['name'] == PRESET_NAMES[idx]` always, so digit `i+1`'s target and the `i`-th preset row's button target are always the same server. No gap, no new button; verified in `dev/click_ui/p4_gpu_news_button_probe.py`.

**(2026-08-18, rollout sub-milestone 7) Permanent row-1 search bar -- HIGHLIGHT-ONLY, per the approved decision: this pane has NO scroll/viewport infra at all** (`pane_height` is accepted by `_render_pane` but never read -- confirmed by grep before implementing), so there is no jump-to-match. `_gpu_search: search_bar.SearchState`; full drag-select/editor-style-deletion mechanics reused via `search_bar.py`'s generic functions. `n`/`N` (`_jump_gpu_search_match`) cycles `current_idx` ONLY (which on-screen match gets `SEARCH_CURRENT_BG` vs `SEARCH_MATCH_BG`, and the N/M counter) -- ZERO scroll call, since there's nothing to scroll to. `_gpu_search_on_commit` (the Enter callback) calls `_render_pane` ONCE without search kwargs (plain baseline, `pane_height=0` since it's never read) to get exactly what the real render would show, splits on `\n`, ANSI-strips each line, and collects 0-based indices containing the query -- no separate matcher function needed (no collapse/expand state to force-open, everything is always fully shown).

**(2026-09, gpu-pane-split milestone) `pane.py` (was 459 LOC, over the 400 ceiling) split into 3 modules by concern — `gpu_actions.py` (server control: `TOGGLE_TIMEOUT`, `_toggle_state`, `_expire_toggle_states`, `_fire_button`) and `gpu_render.py` (rendering: `_button_regions`, `_render_pane` and every helper it calls) moved out; `pane.py` itself kept the event loop, the inline-dispatch-turned-`_handle_gpu_mouse`, and the search wrappers.** `run_gpu_loop` (was 136 LOC, HARD) and `_render_pane` (was 110 LOC, HARD) both needed real multi-step extraction, not one cut, to get under 50 — see those two modules' own entries. **`_toggle_server` is the ONE function in the "server control" concern that stayed in `pane.py` rather than moving to `gpu_actions.py`:** it reads the module-level `PRESET_NAMES` bare-name (imported from `status.py`), and `dev/click_ui/p4_gpu_news_button_probe.py` monkeypatches `mod_gpu.PRESET_NAMES` directly before calling `_toggle_server(idx, presets)` (unchanged 2-arg signature) — a copy of `PRESET_NAMES` imported separately into `gpu_actions.py` would never see that monkeypatch, so the function had to stay where the patchable name lives. `run_gpu_loop`'s inline mouse-dispatch (the `if button == 0: ...` block, real-button-event case only — release/cancel handling stays inline in the poll loop, mirroring `token_pane._poll_tokens_input`'s own precedent) became `_handle_gpu_mouse(button, col, row) -> (input_changed, force_refresh_hit)`, `run_gpu_loop`'s own drain loop became `_poll_gpu_input(...)` (stays local — monkeypatch constraint), the status+collections refresh became `_refresh_gpu_data(...)` (single combined helper, mirrors `token_pane._refresh_tokens_data`/`warnings_pane._refresh_warnings_data`'s pattern), and the render+shift+diff+print tail became `_build_gpu_output(...)`.

### gpu_actions.py (removed heading annotation)

Heading was: `### gpu_actions.py (44 LOC, new 2026-09, gpu-pane-split milestone)`. Purpose text noted: "moved out of `pane.py`."

### gpu_render.py (removed heading annotation and milestone paragraphs)

Heading was: `### gpu_render.py (178 LOC, new 2026-09, gpu-pane-split milestone)`.

**(2026-07-30) New `[refresh]` header button:** appended to the `GPU Servers` title line (row 1, disjoint from every preset/arbitrary button which start at row >= 2), registered in `_button_regions` under a distinguishing `('refresh', 'refresh')` action/target pair — `pane.py`'s `_handle_gpu_mouse` special-cases `action == 'refresh'` (returns `force_refresh_hit=True`) BEFORE the pre-existing `target not in _toggle_state: _fire_button(...)` branch, so it never reaches `_fire_button` (which has no refresh verb). Width-guarded with a REAL gate (no button text and no region when it doesn't fit) — unlike the pre-existing per-server buttons, which use `pad = max(1, ...)` and always register regardless of fit (a pre-existing gap, left untouched, out of scope). **(2026-07-30 review fix) Decoration yields to the button, not the reverse:** `utils.compute_header_rule_len('  GPU Servers', '[refresh]', 64, pane_width)` shrinks the rule first (down to a 4-char minimum) to make room for the button; the button is only omitted when even the shrunk-to-minimum rule plus the button can't fit alongside the title. Crossover: button visible from pane_width >= 27; title text always renders regardless of width (this pane never calls `truncate_visible` on its lines). Verified with a width sweep in `dev/click_ui/p4_gpu_news_button_probe.py`. **No sentinel needed for search highlighting** — this pane has no per-row background/zebra/hover loop at all (lines are plain ANSI-colored text, always the terminal's own default background), so `utils.highlight_query_in_line`'s default `restore_bg='\\033[49m'` is directly correct, same simple case as `core/monitor_display.py`'s main pane. `_render_pane`'s OWN `_button_regions` row numbering stays UNSHIFTED, relative to its own top (row 1 = its own first line) -- `pane.py`'s `_build_gpu_output` shifts every region by `+_GPU_SEARCH_BAR_LINES` EXTERNALLY, after `_render_pane` returns (mirrors `worker_proxy_pane.py`'s identical rebuild-then-shift precedent) -- keeps `_render_pane` a reusable, standalone, directly-testable unit; `dev/click_ui/p4_gpu_news_button_probe.py` (which calls `_render_pane` directly) needed ZERO changes.

**(2026-09, gpu-pane-split milestone) `_render_pane` (was 110 LOC, HARD) split into one helper per section, itself now a thin orchestrator (15 LOC):** `_build_status_row(...)` — the shared row-builder, parameterized by prefix/name_width/button/action/target, used by both `_render_preset_rows` and `_render_arbitrary_rows` — these two were near-duplicate row-builders before the split, differing only in 5 values; `_render_gpu_header`; `_render_collections_block`; `_render_errors_block`; `_render_anomalies_line`; `_apply_gpu_search_highlight` (list-mutation in place, the single post-loop highlight pass). `_render_pane` itself now just calls each in sequence and joins.

### status.py (removed heading annotation, PRESET_NAMES discovery narrative merged into Purpose)

Text merged: `PRESET_NAMES` list discovered at module-import-time via `subprocess.run(['rag-cli', 'server', 'presets', '--json'])` with 3s timeout; returns `[]` on any failure (no fabricated names). `_fetch_collections()` calls `rag-cli list_collections --json` (5s timeout); returns `[{collection, chunks}]`; returns `[]` on any failure (rag-cli absent, Postgres down, JSON error).

### errors.py (removed cross-project sync note)

`ERROR_CODES` mirrors src/rag/error_log.py (RAG) ERROR_CODES — keep in sync on writer-side additions.

### State (removed history annotations)

`gpu_actions.py` (2026-09, moved from `pane.py`); `gpu_render.py` (2026-09, moved from `pane.py`); `_gpu_search: search_bar.SearchState` (2026-08-18); `status.py`'s `_legacy_warned: bool` row and `_check_legacy_files()` detail; `**_toggle_state key convention:**` and `**_button_regions value convention:**` explanatory paragraphs (folded into module Purpose instead).

## Salvage from src/panes/DOCS.md

### Public Interface (removed detail)

`panes/token_search.py` has no `__init__.py` export — imported directly by `token_pane.py` (`from .token_search import build_token_search_matches`).
`panes/log_janitor.py` has no `__init__.py` export — imported directly by `token_pane.py` (`from .log_janitor import cleanup_old_jsonl, sweep_eligible_specs`) and by `dev/hook_smoke/test_log_janitor.py` (via `sys.path.insert`, bare `from log_janitor import`).

### token_pane.py (removed milestone paragraphs)

Owns the zebra/hover/truncation render loop: calls `format_cache_tracker` for logical lines, then applies `ZEBRA_BG_A/B`, `HOVER_BG` priority, and `truncate_visible` per line. Loop follows drain-refresh-render pattern; private helpers `_tokens_ram_state`, `_handle_tokens_mouse`, `_handle_tokens_key`, `_refresh_tokens_data`, `_build_tokens_output` extracted from loop body. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception is caught, logged via `pane_error_log.log_pane_error('tokens')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Copy-by-click on the ⎘ symbol:** `format_cache_tracker` is called with `copy_feedback=_cache_copy_feedback_until` (button-region pattern, mirrors `proxy_display`'s `_proxy_copy_rows`); `_build_tokens_output` detects the rendered `⎘`/`✓` substring per row and populates `cache_copy_rows`. `_handle_tokens_mouse` checks `col >= _cache_pane_width - 2 and row in cache_copy_rows` FIRST (before the pre-existing expand-toggle) — a hit calls `copy_to_clipboard(_serialize_tokens(key))` and sets a 1.5s `✓`-flash entry, identical to the `y` key's `_serialize_tokens` call for the same row.

**(2026-09, panes-split milestone) `build_cache_turns` moved out to `cache_turns.py`** (see that module's own entry) — it was a pure JSONL-turn accumulation function two OTHER real modules (`proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`) import, a data concern rather than a pane concern; `token_pane.py` now imports it back (`from .cache_turns import build_cache_turns`) for its own use in `_refresh_tokens_data`. `run_tokens_loop` (was 67 LOC) and `_build_tokens_output` (was 53 LOC) both dropped under 50: `run_tokens_loop`'s input-drain dispatch (`read_keypress`/`read_mouse_event` bare-name calls) extracted into a same-module top-level `_poll_tokens_input()` — stays physically in this module because `dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` and `dev/pane_search/p6_tokens_pane_parity_test.py` monkeypatch `read_keypress`/`setup_keyboard_input`/`enable_mouse`/`disable_mouse`/`restore_terminal` as attributes of `token_pane` itself, which only works for bare-name lookups made from code physically defined in this module; `_build_tokens_output`'s zebra/hover row-render loop extracted into `_render_tokens_rows(...)`, also same-module (no cross-module reuse case for it — the `Optional` note in the milestone brief explicitly said not to fold this loop with `warnings_render._render_warnings_rows` / `workers/worker_render._render_workers_rows` this round, see Gotchas). `_serialize_tokens`, `_handle_tokens_mouse`, `_handle_tokens_key`, and `_handle_tokens_search_release` all stay in this module for the same monkeypatch/bare-name reason (they call `copy_to_clipboard` bare-name).

**(2026-09) Window 0 is now the tokens pane at full width** (the main pane was removed entirely — see `process-docs/main_pane/`). `run_tokens_loop`'s `_refresh_tokens_data` gained a `last_janitor_ts` param/return threaded through the loop exactly like the old main pane's `run_main_loop` did: every tick, once `now - last_janitor_ts >= 86400`, runs `log_janitor.cleanup_old_jsonl` over `log_janitor.sweep_eligible_specs(Path(__file__).parent.parent / 'logs')` — the tokens pane is always-active and runs from the main checkout (unlike the menubar bundle, which resolves the wrong `logs/` path), the same property that made the main pane the janitor's original host; see `process-docs/logging/log_janitor.md`.

**(2026-08-18, rollout sub-milestone 4) Permanent row-1 search bar, mirroring `proxy_display/pane.py`'s reference implementation** — `_tokens_search: search_bar.SearchState`, thin wrapper functions (`_handle_tokens_search_cancel`/`_input`/`_release`, `_render_tokens_search_bar`), `_tokens_search_on_commit` (Enter callback — data is ALWAYS fully loaded incrementally here, no windowing/reconstruction step unlike the proxy panes, so it just calls `token_search.build_token_search_matches` directly over `_cache_turns`; always re-runs, no unchanged-query gate), `_jump_tokens_search_match`/`_ensure_tokens_match_visible` (`n`/`N` — mirrors `core/monitor_display.py`'s simpler `ensure_match_visible` pattern, NOT the proxy panes' defer-to-next-render `_proxy_just_expanded` dance, since there's no lazy-load to interleave with a scroll here). `_ensure_tokens_match_visible` reads `_tokens_nav` (key → absolute line index + `'total_lines'`, populated fresh by `format_cache_tracker`'s `nav_out` param on every render — not part of `SearchState`, pane-specific) to compute a scroll offset the same way the main pane's `_search_all_line_offsets`/`_search_total_lines` do; relies on at least one prior render having populated it (same accepted staleness tolerance as the main pane's own design — positions don't depend on scroll/search state, only on `_cache_turns`/`cache_expand_states`).

**The sentinel bug, same class as the proxy pane.** `colors.ZEBRA_BG_A == ''` (2026-09 constants-split milestone — moved from `constants.ZEBRA_BG_A`) is the `chosen_bg` for every non-hovered, non-`LIGHT_RED_BG` row and every expanded-detail line. `format_cache_tracker` embeds search highlights with `search_bar._BG_RESTORE_SENTINEL` (not a hardcoded color) at construction time; `_build_tokens_output`'s own hand-rolled row loop calls `search_bar.resolve_bg_restore(line, chosen_bg)` right after `chosen_bg` is chosen (unconditional, no-ops when the sentinel isn't present) — exact same fix shape as `process-docs/pane_search/2026-08-18_highlight_flood_empty_bg_fix.md`. **Collateral fix in the same loop:** the pre-existing `LIGHT_RED_BG` (cc_broken row) detection changed from `line.startswith(LIGHT_RED_BG)` to `LIGHT_RED_BG in line` — a container-marked search match now prepends `marker` before `_format_cache_call`'s own `LIGHT_RED_BG` prefix, so a literal prefix-check would miss it when both conditions co-occur; a substring check still finds it, and is provably equivalent to the old prefix check whenever no marker is present (i.e. byte-identical for every non-search-match row).

**2-row header:** `format_cache_tracker`'s optional `sticky_header` (row 1 when scrolled, before this milestone) now shifts to row 2 — `_TOKENS_SEARCH_BAR_LINES = 1` (fixed) always wins row 1. `format_cache_tracker`'s own internal viewport reservation (`_compute_cache_viewport`'s `pane_height - 1`, reserved for the sticky-header slot whether used or not) is UNTOUCHED — `_build_tokens_output` computes `content_height = pane_height - _TOKENS_SEARCH_BAR_LINES` and passes THAT as `format_cache_tracker`'s own `pane_height` argument, same "caller subtracts its own header rows, the renderer's internal reservation stays put" convention the proxy panes already established. `phys_row` (this pane's own local row counter, no separate shift-dict-after-the-fact step needed since `cache_line_map`/`cache_copy_rows` are built fresh from the correct starting value every render) starts at `1 + _TOKENS_SEARCH_BAR_LINES + (1 if sticky_header else 0)`.

**Known limitation (documented, not fixed):** `_compute_cache_viewport`'s sticky-header truncation path can silently drop a search highlight in the narrow combination of "matching turn" + "long enough to truncate" + "currently the sticky header" — see `format/DOCS.md`'s `token_format.py` entry for the mechanism.

### cache_turns.py (removed heading annotation and split narrative)

Heading was: `### cache_turns.py (57 LOC, new 2026-09, panes-split milestone)`. Purpose narrative: Split out of `token_pane.py` (moved, not rewritten) because it is a pure JSONL-turn accumulation/merge function with no pane-loop or module-state coupling — a data concern, shared by `proxy_display/pane.py` and `proxy_display/worker_proxy_pane.py` in addition to `token_pane.py` itself, not a pane concern. `build_cache_turns` (was 53 LOC) dropped under 50 by extracting the duplicate-call merge block (the "last existing turn was incomplete — merge its api_calls with the fresh parse" branch) into `_merge_duplicate_turn(existing_turns, new_turns) -> list`.

### token_search.py (removed heading annotation)

Heading was: `### token_search.py (35 LOC, new 2026-08-18, rollout sub-milestone 4)`.

### warnings_pane.py (removed milestone paragraphs)

`_errors_record_to_display(rec)` converts raw `_errors` records to display dicts; `_read_errors_log(path, last_pos)` does incremental line-by-line reads. No zero_results, schema_warnings, or dedup sets. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception is caught, logged via `pane_error_log.log_pane_error('warnings')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Copy-by-click on the ⎘ symbol:** `_build_warnings_output` passes `copy_feedback=_error_copy_feedback_until, copy_rows_out=error_copy_rows` into `_format_warnings_pane`. `_handle_warnings_mouse` checks `col >= _error_pane_width - 2 and row in error_copy_rows` FIRST (before the pre-existing expand-toggle) — a hit calls `copy_to_clipboard(_serialize_warnings(ekey, tool_errors))` and sets a 1.5s `✓`-flash entry. This surfaced a pre-existing `y`-key bug (see `warnings_render.py`): `error_line_map` stores a bare int, but `_serialize_warnings` expected a `('error', idx)` tuple — `y` silently copied `''` for every row until fixed here. **(2026-07-30) `[refresh]` header button:** `_build_warnings_output` now computes `header = _format_warnings_header(_last_refresh_ts, pane_width, _warnings_header_regions)` ONCE and threads it into `_format_warnings_pane` as a plain `header: str` param (replacing that function's own internal `last_refresh_ts`-based header construction) — `_build_warnings_output` now returns `(output, header)`, and `run_warnings_loop`'s overdraw print reuses that SAME returned header instead of recomputing `_format_warnings_header` a second time with different args (which would have silently dropped the button on the overdraw pass).

**(2026-09, panes-split milestone) `run_warnings_loop` (was 71 LOC) dropped under 50** by extracting the input-drain dispatch (`read_keypress`/`read_mouse_event` bare-name calls) into a same-module top-level `_poll_warnings_input()` — stays physically in this module for the same monkeypatch reason as `token_pane.py`'s `_poll_tokens_input` (see that module's entry).

**(2026-08-18, rollout sub-milestone 6) Permanent row-1 search bar, mirroring `proxy_display/pane.py`'s reference implementation.** `_warnings_search: search_bar.SearchState`, full mechanics via thin wrappers. `_warnings_search_on_commit` (Enter callback) — data is ALWAYS fully loaded (`tool_errors` accumulates every polled error, no windowing) — calls `warnings_render.build_warnings_search_matches` directly; always re-runs. `_jump_warnings_search_match` (`n`/`N`) cycles `current_idx` only — this pane HAS real scroll infra (`error_scroll_offset`, wheel-driven) but n/N deliberately never touches it, matching the reduced scope also used for gpu/news (a real jump-to-match, auto-scrolling to the match, was judged out of scope for this bundled milestone — flagged, not silently omitted). `_handle_warnings_mouse` now checks `row == 1` (search bar) FIRST, then clears any lingering drag-selection before falling through to the (now row-shifted) `_warnings_header_regions` check, then copy/expand — `_warnings_header_regions`'s `[refresh]` region shifts from row 1 to row `1 + _WARNINGS_SEARCH_BAR_LINES` (rebuild-then-shift, mirrors `worker_proxy_pane.py`'s identical pattern) since `_format_warnings_header` itself still registers at its own row 1. `_build_warnings_output` passes `header_lines=1 + _WARNINGS_SEARCH_BAR_LINES` into `_format_warnings_pane` (generalizes what used to be a hardcoded single-header-row assumption there) and composes the 2-line `header` (`search_bar_line + '\n' + refresh_header`) fed into the PRE-EXISTING overdraw print unchanged.

### warnings_render.py (removed milestone paragraphs)

`_format_warnings_header(last_refresh_ts, pane_width=80, regions_out=None)` builds the header line — **(2026-07-30)** now also appends a `[refresh]` button (WHITE, next to the pre-existing `[r]efresh · last: ... · polling: ...` text, unchanged) and, when `regions_out` given, registers its `(start_col,end_col,phys_row=1)` region (relative to its OWN top — shifted externally by `warnings_pane.py` since 2026-08-18) — but ONLY when it fits `pane_width`; when it doesn't, neither the button text nor the region is added. `_serialize_warnings(key, tool_errors)` formats clipboard output for a single error entry — **(2026-07-30 fix)** `key` is the bare `int` `error_line_map` actually stores, NOT the internal `('error', idx)` tuple `_format_warnings_pane`'s own `all_keys` uses.

**(2026-09, panes-split milestone) `_format_warnings_pane` (was 97 LOC) split into 3 helpers, itself now a thin orchestrator (31 LOC) under its own unchanged name:** `_build_one_warning_lines(...)` — the header line + optional expanded-detail lines for ONE error; `_build_warnings_lines(...)` — loops `_build_one_warning_lines` over the whole `tool_errors` list; `_render_warnings_rows(...)` — the viewport-clipped zebra/hover row loop, carrying the `DIM_YELLOW_BG in line` check. The zebra/viewport loop DID move this round (unlike `token_pane.py`'s equivalent, which stayed in-module by default) — `dev/pane_search/p8_warnings_gpu_news_parity_test.py`'s `inspect.getsource` check on that literal substring was re-pointed from `_format_warnings_pane` to `_render_warnings_rows` in the same commit (Main-approved deviation from the milestone's default "don't fold render loops" stance, since this one has an explicit test dependency forcing the move rather than a discretionary reuse case).

**(2026-08-18, rollout sub-milestone 6) Search-highlight embedding — VERIFIED before assuming anything, per the milestone's own explicit requirement: the row-bg loop already used `DIM_YELLOW_BG in line` (substring), NOT `.startswith()` — unlike every prior pane in this rollout, no collateral fix was needed here.** `ZEBRA_BG_A == ''` DOES still apply (same shared constant as every other pane) — `search_bar.resolve_bg_restore(line, chosen_bg)` threaded into this same (already-correct) loop. `header_lines: int = 1` (new param, default preserves every pre-existing caller's exact behavior) generalizes what used to be a hardcoded `header_offset = 2` — `warnings_pane.py` passes `header_lines=2` (search bar + `[refresh]`). `search_match_set`/`search_current_key` hold a bare `int` err_idx (no nesting — one expand level, matches `error_line_map`'s own key shape). A match's header line is container-marked UNCONDITIONALLY (`marker+line+_BG_RESTORE_SENTINEL`, mirrors `token_format`'s turn-header treatment) — BEFORE `append_copy_symbol`. When expanded, the matching detail lines (`tool_call_input` k/v + the `full_text`/`highlight_stripped` body) ADDITIONALLY get browser-find substring-highlighted via `utils.highlight_query_in_line`. New `build_warnings_search_matches(query, tool_errors)` — the match key IS the bare `err_idx` — checks the underlying dict fields (`tool_name`, `worker_name`, `tool_call_input`, `full_text`) directly rather than re-rendering (this pane's render is trivial, no branching to risk diverging from), covering the FULL untruncated `full_text` regardless of collapsed/expanded display state.

### log_janitor.py (removed provenance sentence)

Moved here 2026-09 from `src/log_janitor.py` because `token_pane.py` is its only in-tree importer and no external entry point loaded it at root (see `process-docs/main_pane/` and `process-docs/logging/` for why it left the now-removed main pane originally).

### Gotchas (removed items)

- `build_cache_turns()` lives in `cache_turns.py` (moved out of `token_pane.py`, 2026-09 panes-split milestone) and is called by `proxy_display/pane.py` + `proxy_display/worker_proxy_pane.py` in addition to `token_pane.py` itself — a shared data-concern utility, not pane-loop code, which is exactly why it moved.
- Zebra/hover/truncation render loop lives in `_render_tokens_rows()` (called from `_build_tokens_output()`) in `token_pane.py`, NOT in `token_format.py`. `format_cache_tracker` returns a uniform 5-tuple `(visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)` on all paths including empty turns (fixed 2026-05-12, commit `1f887ae`) — this shape is unchanged even after the 2026-08-18 search-highlight params (all optional, `nav_out` is an out-param not a return value).
- **(2026-08-18)** `warnings_pane.py`'s search-bar migration is the ONLY one in this rollout that needed ZERO sentinel-detection collateral fix — `warnings_render.py`'s `DIM_YELLOW_BG in line` check already used the substring form before this milestone touched it (verified by reading the source directly, per the milestone's own explicit requirement — see `process-docs/pane_search/`). `ZEBRA_BG_A == ''` still required `search_bar.resolve_bg_restore` in that same loop, same as every other pane.

## Salvage from src/workers/DOCS.md

### Role/Flow (removed milestone paragraph)

**(2026-09, helper-extraction milestone)** `worker_pane.py` split by concern into four sibling modules to stay under the 400-LOC file limit and the 50-LOC helper-extraction threshold: `worker_selection.py` (selection IPC path + write), `worker_clipboard.py` (clipboard serialization), `worker_render.py` (pure viewport/row-render + jump-scroll computation), `worker_search.py` (search on_commit reconstruction). Module-level STATE stays in `worker_pane.py` exclusively (dev probes read/mutate it by attribute); every function that rebinds a scalar global (`worker_selected_name`, `worker_hover_row`, `_worker_pane_width`) or performs a monkeypatch-sensitive bare-name call (`find_worker_jsonl`, `copy_to_clipboard`, `read_keypress`) also stays in `worker_pane.py` — see that module's own entry and `process-docs/proxy_display/` (the prior milestone's proxy-display split, whose constraints this one mirrors) for the reasoning.

### worker_format.py (removed milestone paragraphs)

**(2026-07-30) Copy symbol on both row kinds:** `format_workers_block` takes `copy_feedback: Optional[dict] = None` — a flat dict mixing `str` name keys (worker header row) and `(name,turn_idx,call_idx)` tuple keys (expanded cache-call rows). Header row: `append_copy_symbol(header_line, ..., pane_width)` when `copy_feedback` given. Cache rows: `_worker_cache_copy_feedback(copy_feedback, name)` filters the flat dict down to a `(turn_idx,call_idx)→expiry` sub-dict scoped to THIS worker (avoids cross-worker key collision) before passing it to `format_cache_tracker(..., copy_feedback=...)`. **(2026-07-30) `[LIVE]`/`[FROZEN]` badge as the freeze button:** `regions_out: Optional[dict] = None` param — when given, registers `regions_out['freeze'] = (start_col, end_col)` (COLUMN SPAN ONLY, no row — `format_workers_block` doesn't know the final phys_row, that's resolved by the caller after viewport clipping, see `worker_pane.py`), width-guarded (`pane_width` computed BEFORE the `if not workers:` early return, so both branches can use it): the badge text itself is pre-existing, ALWAYS rendered regardless; only the region registration is gated on whether it fits.

**(2026-08-18, rollout sub-milestone 5) Search-highlight embedding + composition with `format_cache_tracker`.** `format_workers_block` gains `search_match_set`/`search_current_key`/`search_query` — keys are worker-TAGGED (same shape `worker_pane.py`'s `_worker_search.matches` holds): bare `str` name (worker-level match — text is `name + purpose`), `(name, 'turn', turn_idx)`, or `(name, turn_idx, call_idx)` (REUSES the exact 3-tuple shape this module already built for cache rows — zero new shape). A worker-level match container-marks the `header_line` UNCONDITIONALLY (`marker+line+search_bar._BG_RESTORE_SENTINEL`, mirrors `token_format`'s turn-header treatment) — BEFORE `append_copy_symbol`, so the copy button stays outside the marked span. For the nested per-worker view, `_scope_matches_to_worker(matches, name)` / `_scope_current_key_to_worker(current_key, name)` strip the leading worker name and convert to `token_format`'s own shape, filtered to keys belonging to THIS worker only — critical: a match belonging to a DIFFERENT worker must never highlight in this worker's own view — then thread straight into the EXISTING `format_cache_tracker(...)` call, which does 100% of the collapsed-container-mark / expanded-substring-highlight work internally. Zero new highlighting logic needed for the nested view itself.

**(2026-09, helper-extraction milestone) `format_workers_block` (was 121 LOC) split into helpers, same output byte-for-byte:** `_register_freeze_region(...)` (the freeze-badge column-span registration); `_build_worker_header_line(...)` (status/context-%/spawned/model/tokens suffixes + search-mark + copy symbol — reads the new module constant `_STATUS_COLORS`, hoisted out of the per-call dict literal the old body rebuilt every worker); `_build_worker_purpose_line(...)`; `_render_worker_expanded_view(...)` (the nested cache-tracker call + key re-tagging); `_render_worker_row(...)` (wires the previous three together for one worker, including the trailing blank-line separator). `format_workers_block` itself is now the top-level loop over `_render_worker_row` plus the empty-workers/freeze-region setup. Byte-identical — verified via `dev/workers/format_byte_identity.py`.

Trailing line: `New private helpers (same module): _register_freeze_region, _build_worker_header_line, _build_worker_purpose_line, _render_worker_expanded_view, _render_worker_row (2026-09).`

### worker_selection.py (removed heading annotation and provenance sentence)

Heading was: `### worker_selection.py (25 LOC, new 2026-09, split out of worker_pane.py — see process-docs/proxy_display/ for the split-methodology precedent)`. Purpose text: Moved out of `worker_pane.py` verbatim; never referenced by exact name in any dev probe (only called through it), so free to relocate. `worker_pane.py` imports both names (genuinely used internally, not a re-export shim) so `..workers.worker_pane.get_selection_file_path` — the fixed import path `proxy_display/worker_proxy_pane.py` uses — still resolves unchanged; `src/workers/__init__.py`'s own `from .worker_pane import ..., _write_selection as write_selection` line also needed no change for the same reason.

### worker_clipboard.py (removed heading annotation and provenance sentence)

Heading was: `### worker_clipboard.py (34 LOC, new 2026-09, split out of worker_pane.py)`. Purpose text: Gained an explicit `worker_turns: dict` parameter in the split (was a bare module-global read in `worker_pane.py` before) — mirrors `proxy_pane_shared._serialize_proxy_entry(key, entries)`'s own explicit-argument shape; both call sites in `worker_pane.py` now pass `worker_turns` explicitly. Never referenced by exact name in any dev probe.

### worker_render.py (removed heading annotation and provenance detail)

Heading was: `### worker_render.py (97 LOC, new 2026-09, split out of worker_pane.py)`. Purpose text noted `_workers_terminal_size()` — raw `(term.lines, term.columns)` (no `-1` adjustment, unlike `proxy_pane_shared._terminal_size`); `_resolve_workers_hover_key` — "moved from `worker_pane.py`, gained the two map params instead of reading module globals"; `apply_scroll` — "moved out of `_handle_workers_mouse`'s wheel branch; safe to relocate since it has no scalar-global rebind"; `compute_jump_scroll_offset` — "moved out of `_jump_to_workers_match`'s tail... pure given its four inputs". "None of these five are referenced by exact name in any dev probe."

### worker_search.py (removed heading annotation and provenance detail)

Heading was: `### worker_search.py (36 LOC, new 2026-09, split out of worker_pane.py)`. Purpose text: "moved out of `worker_pane._workers_search_on_commit`" and the extended rationale for why `load_turns_fn` must stay `worker_pane._load_worker_turns` (dev/pane_search/p7's monkeypatch target).

### worker_pane.py (removed heading annotation and extensive milestone narrative)

Heading was: `### worker_pane.py (330 LOC, split by concern 2026-09 — see worker_selection.py/worker_clipboard.py/worker_render.py/worker_search.py entries above and process-docs/proxy_display/ for the split-methodology precedent)`.

Removed narrative (very long — full 2026-07 through 2026-09 change history of this module):
- The drain-refresh-render structural description with helper-by-helper extraction history (`_poll_workers_input`, `_handle_workers_mouse`, `_handle_workers_key`, `_refresh_workers_data`, `_build_workers_output`, `_workers_ram_state`, `_load_worker_turns`/`_parse_worker_turns` consolidation history).
- "**The `while True:` body has always been wrapped in its own `try/except Exception:`** — the reference pattern the other 7 pane loops were retrofitted to match (2026-07-31)."
- "**(2026-07-31 fix)** the except clause previously wrote the traceback with an inline `open('/tmp/monitor_cc_error.log', 'a')` — a failing write (disk full, permissions) would have propagated out of the except block itself and killed the loop, since nothing wrapped it; now delegates to `pane_error_log.log_pane_error('workers')`."
- "**(2026-07-30) Row click now selects, not just expands:**" full paragraph on `_handle_workers_mouse` signature/behavior history.
- "**(2026-07-30) Copy-by-click on the ⎘ symbol, both row kinds:**" full paragraph.
- "**Bug found + fixed in the same pass:**" paragraph about `_handle_workers_key`'s `y`-branch and `resolve_parent_key` fallback being dead code, replaced by `worker_render._resolve_workers_hover_key`.
- "**(2026-07-30) Freeze badge as a clickable button:**" full paragraph on `_handle_workers_mouse`'s signature change.
- "**(2026-08-18, rollout sub-milestone 5) Permanent row-1 search bar...**" full paragraph including the ~200ms measured reconstruction cost citation and the `(2026-09)` follow-up note about `worker_search.workers_search_on_commit`.
- "**Jump-to-match (`_jump_to_workers_match`) respects the dormant pane-level scroll — deliberately.**" full paragraph.
- "**No worker-switch reset analog — considered, declined, documented as a design choice, not an oversight.**" full paragraph (partially retained in the rewritten Gotchas, trimmed of history framing).
- "**Collateral fix, same shape as the tokens pane:**" full paragraph, including the "**Found during this same pass, NOT fixed (pre-existing, unrelated to search):**" sub-paragraph about the 2-space indent making the `LIGHT_RED_BG` prefix check pre-existing dead code (partially retained in the rewritten Gotchas, trimmed of history framing).

### State (removed history annotations)

`_worker_header_regions` row description: "row is now `1 + _WORKERS_SEARCH_BAR_LINES` (was `1`) since 2026-08-18". `_worker_search: search_bar.SearchState` annotated "(2026-08-18)". Trailing paragraph: "Mutated by `run_workers_loop`'s private helpers ... — all still defined in `worker_pane.py` itself (2026-09 split moved only the STATE-FREE computation out; every scalar-global rebind and monkeypatch-sensitive call stayed local, see that module's own entry) — no external mutators."

### Gotchas (removed history framing)

`worker_scroll_offset` Gotcha originally read: "**`worker_scroll_offset` (pane-level int) is dormant.** Wheel 64/65 events write to `worker_scroll_offsets[name]` (per-worker dict), which `format_cache_tracker` reads to scroll the expanded REQ view. `worker_scroll_offset` stays permanently 0 — `vp_start = max(0, total_lines - content_height - worker_scroll_offset)` (was `pane_height`, now `content_height = pane_height - _WORKERS_SEARCH_BAR_LINES` since 2026-08-18) reduces to a bottom-anchor. The int is not removed because it anchors the `all_lines[vp_start:vp_start + content_height]` slice-cap that prevents terminal overflow with many workers. **(2026-08-18) Jump-to-match deliberately never touches it either** — see `worker_pane.py`'s own module entry for the reasoning."

## 2026-09-11 — recap

Main session. Task scope was exactly the 11 DOCS.md files listed above; no `.py`/`.sh`/other
source file was read for editing purposes beyond the read-only investigation needed to derive the
rewritten DOCS.md content from the actual code. `git diff integration --name-only` at recap time
shows only this process-docs file plus the 11 DOCS.md files — no source file was touched, so the
worker-rules "DOCS.md currency check for every `src/`/`dev/` file touched" has no additional
target beyond the DOCS.md rewrite that was the task itself.

Verification performed before the initial commit, not repeated here since nothing changed since:
- `wc -l` on every `.py`/`.sh` module named in a rewritten heading matched the heading's LOC value exactly (47 modules across the 11 files).
- `docs-drift-check` run from this worktree: zero Path-Drift/LOC-Drift/Symbol-Drift findings for any of the 11 rewritten files except `src/DOCS.md:143`/`:147` (`bin/worker-cli` — correctly annotated `(iterative-dev)` per the cross-project-path convention; the checker doesn't parse that annotation, same false positive already present at `src/menubar/DOCS.md:126`) and `src/DOCS.md:145`/`:162` + `src/ccwrap/DOCS.md:56` (`src/logs`/`src/logs/ccwrap` — gitignored runtime-only directories, the same pre-existing false-positive pattern repeated in ~40 other DOCS.md files across the repo).
- Every `Called by` line was derived from a fresh grep over `src/` and `dev/` for the module's actual export names (not copied from the pre-existing prose) — no DEAD CODE candidate was found among the 47 modules in scope.

No corrections were needed in this recap pass. The rewritten DOCS.md content and the salvage
sections above stand as committed in `aa4125e`.
