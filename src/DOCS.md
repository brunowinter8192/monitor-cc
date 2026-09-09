# src/ — Monitor_CC

## Role

Real-time monitor for Claude Code sessions. Reads Claude Code's JSONL output files and the mitmproxy API log, formats tool calls and events to a terminal, and drives 8 dedicated tmux panes (tokens, warnings, workers, worker-proxy, proxy, gpu, news, news-log). The `src/` tree is the entire application — `workflow.py` at the project root is just a 25-line entry point.

## Entry Points

- `workflow.py` → `src.startup`, `src.tmux_launcher`, `src.core.monitor`
- mitmproxy → `src.proxy_addon` (thin shim, loaded via `mitmproxy -s src/proxy_addon.py`)
- tmux panes → `workflow.py --mode <pane>` (each pane is a separate process)

## Directory Map

| Subdir | Role | LOC | Modules |
|---|---|---|---|
| `core/` | Session discovery + mode dispatcher (main pane removed 2026-09, see `process-docs/main_pane/`) | 121 | 1 |
| `panes/` | Tmux pane event loops (tokens, warnings) + warnings scan/render/parse helpers + tokens search matcher | 1207 | 5 |
| `format/` | ANSI string rendering (cache tracker) | 324 | 2 |
| `input/` | Keyboard/mouse stdin handling | 150 | 1 |
| `jsonl/` | JSONL parsing (incremental read + cache-turn extraction) | 206 | 2 |
| `workers/` | Workers pane (tmux session discovery + status display) | 878 | 3 |
| `proxy_display/` | Proxy pane TUI (two-level expand, delta rendering, subprocess-parse, copy-button) | 2892 | 8 |
| `proxy/` | mitmproxy addon (payload modification + JSONL logging) | 3074 | 18 |
| `ram_audit/` | SIGUSR1 RAM-dump helper, gated by MONITOR_CC_RAM_AUDIT env | 121 | 1 |
| `menubar/` | macOS status-bar app showing live CC sessions (rumps/AppKit) | 4155 | 25 |
| `gpu_pane/` | GPU server monitor pane (cross-project, reads RAG state) | 734 | 3 |
| `news_pane/` | CoinDesk news pipeline control (left) + live log tail (right) | 501 | 3 |
| `hooks/` | Global CC safety hooks (PreToolUse scripts + hook_setup) | 1674 | 22 |
| `ccwrap/` | Standalone PTY wrapper with diagnostic ANSI logging for CC (Phase 1 diagnostic tool) | 254 | 4 |

## Root-Level Files

| File | LOC | Why at root |
|---|---|---|
| `constants.py` | 154 | Imported by ~all subpackages — shallow path avoids deep `...constants` chains |
| `utils.py` | 190 | Same — `format_timestamp` + `visual_line_count` used everywhere; also `append_copy_symbol` (right-align a ⎘/✓ symbol, width-guarded — shared by `core.monitor_display`, `format.token_format`, `panes.warnings_render`, `workers.worker_format`, and `proxy_display`'s own reference implementation stays independent), `compute_header_rule_len` (shrinking-decoration header layout, shared by `gpu_pane`/`news_pane`), `highlight_query_in_line` (2026-08, browser-find-style inline substring BG highlight, ANSI-safe; `restore_bg` param defaults to `\033[49m` for callers with no per-row background — used directly by `core.monitor_display` since 2026-08-18 (its own identical private copy was deleted, rollout sub-milestone 2) and by `format.token_format` since sub-milestone 4 (passed a `search_bar._BG_RESTORE_SENTINEL` restore_bg, since the tokens pane DOES have a per-row background); `search_bar.py` passes a caller-owned sentinel instead, substituted for the real row background once known, for panes WITH a per-row background), and `wrap_visible` (2026-08-28, thinking-expander milestone — the repo's first word-wrap helper, cell-aware via `_cell_width` like `truncate_visible`, NOT character-count-based; breaks on spaces, hard-splits a single word wider than the target width; currently used only by `proxy_display/render_messages.py`'s thinking-block content wrapping) |
| `search_bar.py` | 215 | Shared search-bar mechanics (2026-08-18, sub-milestone 1 of the pane-search rollout — extracted from `proxy_display/pane.py`, the reference implementation) — `SearchState`, `render_search_bar`, `col_to_query_index`, `handle_search_input`/`_cancel`, the drag-select mouse handlers, and the `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` pair. Imported by `proxy_display` (sub-milestone 1's `pane.py` AND sub-milestone 3's `worker_proxy_pane.py`, 2026-08-18 — the latter imports only `SearchState`/`render_search_bar`/the input+drag handlers, not `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` directly, since that sentinel machinery already lives in the SHARED `format.py`/`render_turn.py` render pipeline both proxy panes call through — worker_proxy_pane's own zebra/hover rows get the same sentinel-based highlight preservation automatically, no separate import needed), `core` (sub-milestone 2, 2026-08-18 — the main pane's `_main_search`), `panes`/`format` (sub-milestone 4, 2026-08-18 — the tokens pane's `_tokens_search`; `format/token_format.py` imports `_BG_RESTORE_SENTINEL` directly to embed search highlights at construction time, `panes/token_pane.py` imports `resolve_bg_restore` to resolve them in its own hand-rolled row loop — same `ZEBRA_BG_A == ''` trap the proxy pane hit, fixed the same way), `workers` (sub-milestone 5, 2026-08-18 — the workers pane's `_worker_search`; same `_BG_RESTORE_SENTINEL`/`resolve_bg_restore` split between `worker_format.py` (embed) and `worker_pane.py` (resolve, own hand-rolled loop) as the tokens pane — third occurrence of the identical sentinel fix), `panes.warnings_pane`/`warnings_render` (sub-milestones 6-8, 2026-08-18, bundled — the warnings pane's `_warnings_search`; fourth sentinel occurrence, `ZEBRA_BG_A==''` still applied even though this pane's PRE-EXISTING `DIM_YELLOW_BG` detection was already substring-based, verified before assuming), and `gpu_pane`/`news_pane` (sub-milestones 7-8, 2026-08-18 — `_gpu_search`/`_news_search`; HIGHLIGHT-ONLY, no jump-to-match, no sentinel needed at all — neither pane has any per-row background/zebra/hover loop, so `utils.highlight_query_in_line`'s default `restore_bg` is directly correct, same simple case as the main pane; `search_bar.py`'s drag-select/editor-deletion functions called directly at each pane's own INLINE mouse/key dispatch, since neither pane factors dispatch into a standalone handler function) — same shallow-path rationale as `constants.py`/`utils.py`. Rollout complete as of sub-milestone 8 — all 8 panes now share this module (`news_pane/log_pane.py` explicitly excluded per decision). See `proxy_display/DOCS.md` and `core/DOCS.md` for each retrofit and `process-docs/pane_search/` for the rollout plan. |
| `pane_error_log.py` | 35 | `log_pane_error(pane_name)` — shared exception-safe sink all 8 pane `run_*_loop()` functions call from their `except Exception:` guard (2026-07-31); imported by every pane module the same shallow-path way as `constants.py`, so it belongs at the same level |
| `session_finder.py` | 85 | Single module, no subpackage warranted |
| `startup.py` | 48 | Single module; only called by `workflow.py` |
| `tmux_launcher.py` | 281 | Single module; only called by `workflow.py` (mode `all` → `launch_split_screen`; mode `restart-panes` → `restart_panes`, the Ctrl+R self-heal handler). **(2026-09, remaining-thresholds milestone)** `launch_split_screen`/`restart_panes` were both over the 50-LOC function threshold — `launch_split_screen` now reuses `_build_mode_commands` for its 8 mode-command strings (was duplicated inline, byte-identical construction) and delegates the window/split sequence to `_create_windows(session_name, cmds)`; `restart_panes` gained `_list_pane_modes(session_name, win_idx)` (the thrice-repeated list-panes+parse), `_create_missing_window(...)`, `_fill_missing_panes(...)`, `_respawn_all_panes(session_name)`. Byte-identical `subprocess.run` argv sequences verified via `dev/tmux_launcher/argv_byte_identity.py`. |
| `monitor_janitor.py` | 93 | `sweep_workflow()` — kills every `monitor_cc_*` tmux session older than 24h (registry-free `tmux list-sessions` enumeration, same lesson as the worker-cli janitor), logs one line per session (name, age, KILLED/SPARED) to `<checkout>/src/logs/monitor_sweep.log`, where `<checkout>` is `$MONITOR_CC_ROOT` if set, else the directory two levels above `monitor_janitor.py`'s own `__file__` — so a manual run from a `.claude/worktrees/<name>/` checkout writes into THAT worktree's `src/logs/`, not the main checkout's, unless `MONITOR_CC_ROOT` is set. No main-checkout fallback like `dual_log_cli.discovery.resolve_dual_log_dir` — this path is a write target that must follow whichever checkout's code produced the entry, not a read source to prefer aggregating in one place. Invoked as `python3 -m src.monitor_janitor` from project root — from `claude_proxy_start.sh` (detached, every main-session start; bash `cd`'s into `$MONITOR_CC_ROOT` first, so `__file__` resolves correctly without an explicit env var) and, 2026-09, from `src/menubar/monitor_sweep_scheduler.py`'s daily tick-gated call (`sweep_workflow()` imported directly, not `-m`; sets `$MONITOR_CC_ROOT` explicitly first, since a frozen py2app bundle's own `__file__` resolves inside the bundle copy). **This module's own dedicated LaunchAgent (`com.brunowinter.monitor-cc-sweep.plist` + `setup_monitor_sweep.py`) was removed 2026-09** — a bare launchd-spawned `/usr/bin/python3` has no TCC Full Disk Access grant for a checkout under `~/Documents`, and that block cannot be worked around by any plist or code change (see `process-docs/monitor_lifecycle/`); the daily run moved to the already-launchd-and-TCC-granted menubar app's own tick instead. Never uses `pkill -f` (see `process-docs/pipeline/` `pkill -f` incident) — kills by exact tmux session name only, which tears down all nine panes (verified in `dev/monitor_lifecycle/`). |
| `proxy_addon.py` | 31 | Thin shim — `claude_proxy_start.sh` copies it to `src/logs/.proxy_addon_live_<id>.py` for per-session isolation. Shim has sys.path logic that finds `src/proxy/` from both root and live-copy locations. Move would break live-copy pattern. |
| `claude_proxy_start.sh` | 436 | Shell script — launches mitmproxy + Claude Code with proxy env; version-aware purge (Phase 0: hash proxy source, delete stale >60min logs on change) + count-30 quartet-aligned dual-log rotation; per-project marker (src/logs + /tmp) with PID+identity liveness guard + 10s heartbeat reclaim; model precedence (highest first): explicit `--model` (anywhere in the args) > `--fable`/`--opus` shortcut flags (2026-08-06, map to `--model claude-fable-5`/`claude-opus-5`, last one wins if both given) > `main` from `~/.claude/shared-rules/model_selection.json` (2026-08, model-selector milestone 3 — the menubar's Models tab writes this file; read via `jq`, `command -v`-guarded; a missing/unreadable/malformed file or missing/empty key falls through silently) > nothing injected, byte-identical to no-flag behavior; fires a fully-detached `worker-cli janitor` (2026-08-19, `command -v`-guarded, `nohup ... & disown`) before arg-parsing so every main-session start also triggers the iterative-dev stale-tmux-worker sweep — see `iterative-dev` repo's `bin/worker-cli`, unrelated to this script's own `_janitor_*` functions (proxy live-copy/log rotation, pre-existing separate concern, same name coincidental); also fires a fully-detached `python3 -m src.monitor_janitor` (2026-09, `cd "$MONITOR_CC_ROOT"` first so the module path resolves regardless of caller CWD) triggering the monitor-session sweep (`monitor_janitor.py`) on the same every-session-start cadence |

## Flow (Main Session)

1. `workflow.py` → `run_monitor(project_filter, mode="all")` → `tmux_launcher.launch_split_screen()` spawns 8 panes each running `workflow.py --mode <X>`. **(2026-09) Window 0 is the tokens pane at full width** — the main pane was removed entirely, see `process-docs/main_pane/`.
2. Each pane runs its own event loop (e.g. `run_tokens_loop()`): poll data source → handle mouse/keyboard → render full screen. `core/monitor.py::run_monitor` only discovers sessions and dispatches to the matching loop by `--mode`; it does not run a loop of its own anymore.
3. mitmproxy (started by `claude_proxy_start.sh`) intercepts API traffic, strips/modifies payloads, logs to `src/logs/api_requests_<id>.jsonl`.
4. Panes that need proxy data (proxy_display, warnings) tail that JSONL file independently.

## Shared State

Runtime state (`file_positions`, `active_project_filter`, `active_mode`) lives in `core/monitor.py` as module-level variables. Every pane that needs session state imports via `from ..core import monitor as _monitor` (lazy, inside the run function to avoid circular imports).

| State | Owner | Readers |
|---|---|---|
| `file_positions` | `core/monitor.py` | `core/monitor.py` itself (session-file bookkeeping only) |
| `active_project_filter` | `core/monitor.py` | all pane loops |
| `active_mode` | `core/monitor.py` | `core/monitor.py` itself |
| Pane scroll/expand state | each pane module | that pane only |

## Subdir DOCS

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
