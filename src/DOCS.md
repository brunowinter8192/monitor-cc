# src/ — Monitor_CC

## Role

Real-time monitor for Claude Code sessions. Reads Claude Code's JSONL output files and the mitmproxy API log, formats tool calls and events to a terminal, and drives 10 dedicated tmux panes (tokens, rules, hooks, warnings, waste, workers, worker-proxy, worker-metadata, proxy, metadata). The `src/` tree is the entire application — `workflow.py` at the project root is just a 25-line entry point.

## Entry Points

- `workflow.py` → `src.startup`, `src.tmux_launcher`, `src.core.monitor`
- mitmproxy → `src.proxy_addon` (thin shim, loaded via `mitmproxy -s src/proxy_addon.py`)
- tmux panes → `workflow.py --mode <pane>` (each pane is a separate process)

## Directory Map

| Subdir | Role | LOC | Modules |
|---|---|---|---|
| `core/` | Session polling orchestrator + main-pane output | 611 | 3 |
| `panes/` | Tmux pane event loops (tokens, rules, warnings, waste) + parsing helpers | 1537 | 6 |
| `format/` | ANSI string rendering (tool calls, events, cache tracker) | 490 | 4 |
| `input/` | Keyboard/mouse stdin handling + rules block renderer | 215 | 2 |
| `hooks/` | Hook log pipeline (parse → filter → enrich → display) | 497 | 4 |
| `jsonl/` | JSONL parsing + tool call extraction | 518 | 3 |
| `workers/` | Workers pane (tmux session discovery + status display) | 501 | 3 |
| `metadata/` | Metadata pane (API config state from proxy log) | 309 | 2 |
| `proxy_display/` | Proxy pane TUI (two-level expand, delta rendering) | 1644 | 8 |
| `proxy/` | mitmproxy addon (payload modification + JSONL logging) | 2474 | 16 |

## Root-Level Files

| File | LOC | Why at root |
|---|---|---|
| `constants.py` | 165 | Imported by ~all subpackages — shallow path avoids deep `...constants` chains |
| `utils.py` | 91 | Same — `format_timestamp` + `visual_line_count` used everywhere |
| `session_finder.py` | 85 | Single module, no subpackage warranted |
| `startup.py` | 47 | Single module; only called by `workflow.py` |
| `tmux_launcher.py` | 178 | Single module; only called by `workflow.py` |
| `proxy_addon.py` | 31 | Thin shim — `claude_proxy_start.sh` copies it to `src/logs/.proxy_addon_live_<id>.py` for per-session isolation. Shim has sys.path logic that finds `src/proxy/` from both root and live-copy locations. Move would break live-copy pattern. |
| `claude_proxy_start.sh` | 205 | Shell script — launches mitmproxy + Claude Code with proxy env |

## Flow (Main Session)

1. `workflow.py` → `run_monitor(project_filter, mode="all")` → `tmux_launcher.launch_split_screen()` spawns 10 panes each running `workflow.py --mode <X>`.
2. The main pane runs `run_main_loop()` (in `core/monitor.py`): every 0.5s discover sessions → for each session read new JSONL lines → classify tool calls → append to `MAIN_EVENT_BUFFER` → flush to stdout via `monitor_display.py`.
3. Each dedicated pane runs its own event loop (e.g. `run_tokens_loop()`): poll data source → handle mouse/keyboard → render full screen.
4. mitmproxy (started by `claude_proxy_start.sh`) intercepts API traffic, strips/modifies payloads, logs to `src/logs/api_requests_<id>.jsonl`.
5. Panes that need proxy data (proxy_display, warnings, waste) tail that JSONL file independently.

## Shared State

All runtime state lives in `core/monitor.py` as module-level variables. Every pane that needs it imports via `from ..core import monitor as _monitor` (lazy, inside the run function to avoid circular imports).

| State | Owner | Readers |
|---|---|---|
| `file_positions`, `call_counter` | `core/monitor.py` | `core/monitor_session.py` |
| `agent_to_task`, `agent_to_type` | `core/monitor.py` | `core/monitor_session.py`, pane loops |
| `active_project_filter` | `core/monitor.py` | all pane loops |
| `hook_log_position` | `core/monitor.py` | `panes/rules_pane.py` |
| Pane scroll/expand state | each pane module | that pane only |

## Subdir DOCS

- [core/DOCS.md](core/DOCS.md) — polling loop, session processing, main-pane display
- [panes/DOCS.md](panes/DOCS.md) — token, rules, warnings, waste pane loops
- [format/DOCS.md](format/DOCS.md) — formatter, formatter_events, token_format
- [input/DOCS.md](input/DOCS.md) — click_handler, ui_mode
- [hooks/DOCS.md](hooks/DOCS.md) — hook_parser, hooks_format, hooks_persist, hooks_pane
- [jsonl/DOCS.md](jsonl/DOCS.md) — jsonl_parser, jsonl_extractors, jsonl_cache_turns
- [workers/DOCS.md](workers/DOCS.md) — worker_pane, worker_format, worker_tmux
- [metadata/DOCS.md](metadata/DOCS.md) — metadata_pane, metadata_format
- [proxy_display/DOCS.md](proxy_display/DOCS.md) — proxy pane TUI (8 modules)
- [proxy/DOCS.md](proxy/DOCS.md) — mitmproxy addon (15 modules)
