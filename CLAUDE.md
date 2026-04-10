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
| Proxy Display | proxy_pane.py | Dedicated tmux pane, API request structure |
| Subagent Display | subagent_pane.py | Dedicated tmux pane, per-agent cache token view |
| Metadata Display | metadata_pane.py | Dedicated tmux pane, API config state (model, tokens, thinking, sampling, cache markers) |

### Key Files

| File | Component |
|------|-----------|
| `workflow.py` | Entry point, mode routing |
| `src/startup.py` | CLI args, signal handlers |
| `src/tmux_launcher.py` | tmux session, 5-window layout |
| `src/monitor.py` | Core polling orchestrator (~460 lines) |
| `src/token_pane.py` | Token profiling pane |
| `src/proxy_pane.py` | Proxy pane + log parsing |
| `src/worker_pane.py` | Workers pane + status detection |
| `src/hooks_pane.py` | Hooks pane + persisted context |
| `src/rules_pane.py` | Rules pane + InstructionsLoaded routing |
| `src/warnings_pane.py` | Warnings pane |
| `src/subagent_pane.py` | Subagent pane |
| `src/metadata_pane.py` | Metadata pane (API config: model, max_tokens, thinking, sampling, cache markers) |
| `src/formatter.py` | Shared tool call formatting (~230 lines) |
| `src/session_finder.py` | Session discovery |
| `src/jsonl_parser.py` | JSONL parsing, tool call extraction |
| `src/hook_parser.py` | Hook log parsing |
| `src/click_handler.py` | Keyboard input handling |
| `src/constants.py` | Shared constants |
| `src/utils.py` | Colors, timestamps |
| `src/proxy_addon.py` | mitmproxy addon (cache_control, tool stripping, rules caching) |
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
│   ├── monitor.py                  → Core polling orchestrator
│   ├── token_pane.py               → Token profiling pane (cache tracker, session browser)
│   ├── proxy_pane.py               → Proxy pane (API request structure, log parsing)
│   ├── worker_pane.py              → Workers pane (status, cache per worker)
│   ├── hooks_pane.py               → Hooks pane (hook events, expand/collapse)
│   ├── rules_pane.py               → Rules pane (active rules, InstructionsLoaded routing)
│   ├── warnings_pane.py            → Warnings pane (unknown JSONL types)
│   ├── subagent_pane.py            → Subagent pane (per-agent cache token view)
│   ├── metadata_pane.py            → Metadata pane (API config state, change detection)
│   ├── session_finder.py
│   ├── jsonl_parser.py
│   ├── hook_parser.py
│   ├── formatter.py                → Shared tool call formatting
│   ├── click_handler.py
│   ├── ui_mode.py
│   ├── subagent_ui.py
│   ├── tmux_launcher.py
│   ├── startup.py
│   ├── constants.py
│   ├── utils.py
│   ├── proxy_addon.py              → mitmproxy addon (cache_control, tool stripping, rules caching)
│   ├── proxy_launcher.sh
│   ├── claude_proxy_start.sh
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
