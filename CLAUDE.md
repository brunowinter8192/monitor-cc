# Monitor_CC

Real-time Claude Code session monitor with TUI dashboard.

## Sources

See [sources/sources.md](sources/sources.md)

## Pipeline Components

### Entry & Startup

| Component | Implementation | Config |
|-----------|---------------|--------|
| CLI Entry | workflow.py → argparse | `--mode all\|main\|subagent\|rules\|warnings\|hooks\|tokens\|workers\|proxy`, `--project`, `--ui` |

| tmux Launch | tmux_launcher.py | 5-Window (main+tokens \| proxy \| rules+hooks \| workers \| warnings), history 50000 |
| Signal Handling | startup.py | SIGINT/SIGTERM → graceful shutdown |

### Data Sources

| Component | Implementation | Config |
|-----------|---------------|--------|
| Session Discovery | session_finder.py | `~/.claude/projects/**/*.jsonl` + `*/subagents/agent-*.jsonl` |
| JSONL Parsing | jsonl_parser.py | tool_use/tool_result pairs, user prompts, media, thinking, skills, usage |
| Unknown Type Detection | jsonl_parser.py | KNOWN_MESSAGE_TYPES + KNOWN_IGNORED_TYPES in constants.py |
| Hook Parsing | hook_parser.py | `src/logs/hook_outputs.jsonl` → UserPrompt, PreTool, InstructionsLoaded |

### Core Loop

| Component | Implementation | Config |
|-----------|---------------|--------|
| Polling | monitor.py `run_streaming_loop` | 0.5s interval |
| Token Profiling | token_pane.py `run_tokens_loop` | Input tokens (direct, cache create, cache read) + output tokens by block type + tool name |
| Hook Routing | rules_pane.py `process_hook_log` / hooks_pane.py `process_hook_log_for_display` | InstructionsLoaded → rules pane, hooks with output → hooks pane |
| Agent Tracking | monitor.py | agent_to_task, agent_to_type, buffered calls |

### Display

| Component | Implementation | Config |
|-----------|---------------|--------|
| Tool Call Formatting | formatter.py | Green (main), Blue (subagent), Red (error) |
| UI Mode Loop | ui_mode.py | Screen-clear refresh, raw stdin |
| Rules Display | rules_pane.py | Pastel blue, [P]/[G] prefix, eigenes tmux Pane |
| Hooks Display | hooks_pane.py | Dedicated tmux pane, scrolling stream, expand/collapse |
| Warnings Display | warnings_pane.py | Dedicated tmux pane, unknown type warnings |
| Token Display | token_pane.py | Dedicated tmux pane, bar chart, session browser (cumulative N sessions) |
| Workers Display | worker_pane.py | Dedicated tmux pane, real-time worker status |
| Proxy Display | proxy_display/ | Dedicated tmux pane, API request structure |
| Subagent Display | subagent_pane.py | Dedicated tmux pane, per-agent cache token view |
| Metadata Display | metadata_pane.py | Dedicated tmux pane, API config state (model, tokens, thinking, sampling, cache markers) |

### Key Files

| File | Component |
|------|-----------|
| `workflow.py` | Entry point, mode routing |
| `src/startup.py` | CLI args, signal handlers |
| `src/tmux_launcher.py` | tmux session, 5-window layout |
| `src/monitor.py` | Core polling orchestrator + state |
| `src/monitor_session.py` | Session processing, agent/task handlers |
| `src/monitor_display.py` | Display helpers (tool calls, prompts, media) |
| `src/token_pane.py` | Token pane event loop + incremental cache turns |
| `src/token_format.py` | Token pane rendering (cache tracker, viewport, scroll) |
| `src/proxy_display/` | Proxy pane TUI package — [DOCS.md](src/proxy_display/DOCS.md) |
| `src/proxy/` | mitmproxy addon package — [DOCS.md](src/proxy/DOCS.md) |
| `src/proxy_addon.py` | Thin entry point for mitmproxy `-s` flag |
| `src/worker_pane.py` | Workers pane event loop + state |
| `src/worker_format.py` | Worker entry formatting |
| `src/worker_tmux.py` | Worker tmux session detection |
| `src/hooks_pane.py` | Hooks pane event loop + state |
| `src/hooks_format.py` | Hook entry formatting |
| `src/hooks_persist.py` | Persisted hook file scanning |
| `src/rules_pane.py` | Rules pane + InstructionsLoaded routing |
| `src/warnings_pane.py` | Warnings pane |
| `src/subagent_pane.py` | Subagent pane event loop + state |
| `src/subagent_render.py` | Subagent pane rendering with token view |
| `src/subagent_ui.py` | Subagent list building + state |
| `src/subagent_ui_format.py` | Subagent entry formatting helpers |
| `src/metadata_pane.py` | Metadata pane event loops |
| `src/metadata_format.py` | Metadata rendering (system, tools, config, cache markers) |
| `src/formatter.py` | Tool call request/response formatting |
| `src/formatter_events.py` | Event formatting (prompts, media, thinking, skills) |
| `src/jsonl_parser.py` | JSONL parsing, tool call extraction |
| `src/jsonl_extractors.py` | Message extractors (prompts, media, thinking, skills, usage) |
| `src/jsonl_cache_turns.py` | Cache turn extraction for token pane |
| `src/session_finder.py` | Session discovery |
| `src/hook_parser.py` | Hook log parsing |
| `src/click_handler.py` | Keyboard input handling |
| `src/constants.py` | Shared constants |
| `src/utils.py` | Colors, timestamps |
| `src/claude_proxy_start.sh` | Combined proxy + Claude Code launcher |

## Project Structure

```
Monitor_CC/
├── workflow.py                     → Pipeline entry point
├── requirements.txt
├── README.md
├── decisions/                      → Pipeline decision records (rationale per implementation choice)
│   ├── pipe01_entry_startup.md
│   ├── pipe02_data_sources.md
│   ├── pipe03_core_loop.md
│   ├── pipe04_display.md
│   └── pipe05_proxy_cache.md
├── sources/                        → [sources.md](sources/sources.md)
├── not_working/                    → Failed approaches (markdown records)
├── repo/                           → tmux source code (external reference, own .git)
├── src/                            → [DOCS.md](src/DOCS.md)
│   ├── monitor.py                  → Core polling orchestrator + state
│   ├── monitor_session.py          → Session processing, agent/task handlers
│   ├── monitor_display.py          → Display helpers (tool calls, prompts, media)
│   ├── token_pane.py               → Token pane event loop + incremental cache turns
│   ├── token_format.py             → Token pane rendering (cache tracker, viewport)
│   ├── worker_pane.py              → Workers pane event loop + state
│   ├── worker_format.py            → Worker entry formatting
│   ├── worker_tmux.py              → Worker tmux session detection
│   ├── hooks_pane.py               → Hooks pane event loop + state
│   ├── hooks_format.py             → Hook entry formatting
│   ├── hooks_persist.py            → Persisted hook file scanning
│   ├── rules_pane.py               → Rules pane (active rules, InstructionsLoaded routing)
│   ├── warnings_pane.py            → Warnings pane (unknown type warnings)
│   ├── subagent_pane.py            → Subagent pane event loop + state
│   ├── subagent_render.py          → Subagent pane rendering with token view
│   ├── subagent_ui.py              → Subagent list building + state
│   ├── subagent_ui_format.py       → Subagent entry formatting helpers
│   ├── metadata_pane.py            → Metadata pane event loops
│   ├── metadata_format.py          → Metadata rendering (system, tools, config)
│   ├── formatter.py                → Tool call request/response formatting
│   ├── formatter_events.py         → Event formatting (prompts, media, thinking)
│   ├── jsonl_parser.py             → JSONL parsing, tool call extraction
│   ├── jsonl_extractors.py         → Message extractors (prompts, media, usage)
│   ├── jsonl_cache_turns.py        → Cache turn extraction for token pane
│   ├── session_finder.py
│   ├── hook_parser.py
│   ├── click_handler.py
│   ├── ui_mode.py
│   ├── tmux_launcher.py
│   ├── startup.py
│   ├── constants.py
│   ├── utils.py
│   ├── proxy_addon.py              → Thin entry point for mitmproxy -s flag
│   ├── claude_proxy_start.sh
│   ├── proxy/                      → [DOCS.md](src/proxy/DOCS.md) mitmproxy addon package
│   │   ├── addon.py                → ProxyAddon class (request/response hooks)
│   │   ├── rules.py                → Payload modification rules
│   │   ├── content_strip.py        → Content stripping helpers
│   │   ├── cache.py                → Cache-control breakpoint logic
│   │   ├── logging.py              → Log entry building
│   │   ├── message_summary.py      → Message classification + summarization
│   │   └── tools.py                → Unused tool stripping
│   ├── proxy_display/              → [DOCS.md](src/proxy_display/DOCS.md) Proxy pane TUI package
│   │   ├── pane.py                 → Event loops (main + worker proxy)
│   │   ├── format.py               → format_proxy_block + helpers
│   │   ├── parser.py               → Proxy log parsing + payload extraction
│   │   ├── render_entry.py         → Standalone entry rendering
│   │   ├── render_turn.py          → Turn-expanded rendering
│   │   ├── render_sections.py      → System blocks + tools rendering
│   │   └── render_messages.py      → Message rendering (new/modified/removed)
│   └── logs/                       → Runtime log files (gitignored)
├── dev/                            → [DOCS.md](dev/DOCS.md)
│   ├── display/                    → [DOCS.md](dev/display/DOCS.md)
│   │   ├── test_tmux_layout.sh
│   │   ├── scan_jsonl_rules.py
│   │   └── screenshot_panes.py     → tmux pane screenshot tool (5-window, 7-pane → PNG)
│   └── session_analysis/
│       ├── 01_extract.py
│       ├── 02_cache_timeline.py
│       └── 03_cache_rebuild_context.py
```
