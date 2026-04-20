# Monitor_CC

Real-time TUI monitor for Claude Code sessions — reads JSONL output and mitmproxy API logs, renders tool calls and events across 10 dedicated tmux panes.

## Sources

See [sources/sources.md](sources/sources.md).

## Code

See [src/DOCS.md](src/DOCS.md) — Directory Map, Flow, Shared State, all subdir DOCS links.

## Decisions

See [decisions/](decisions/) — one file per pipeline component (entry, data sources, core loop, display, proxy/cache).

## Pipeline Overview

1. `workflow.py --mode all` → `tmux_launcher` spawns 10 panes, each running `workflow.py --mode <pane>`.
2. Main pane: `core/monitor.py` polls `~/.claude/projects/**/*.jsonl` every 0.5s, classifies tool calls, prints to stdout.
3. mitmproxy (`src/proxy/`) intercepts API traffic, strips/modifies payloads, logs to `src/logs/api_requests_<id>.jsonl`.
4. Dedicated panes (`panes/`, `hooks/`, `workers/`, `proxy_display/`, `metadata/`) tail their respective data sources and render interactive ANSI TUI.
5. All panes read shared runtime state from `core/monitor.py` via lazy `from ..core import monitor as _monitor`.
