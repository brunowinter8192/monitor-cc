# Monitor_CC

Real-time Claude Code session monitor with TUI dashboard.

## Sources

See [sources/sources.md](sources/sources.md)

## Pipeline Components

### Entry & Startup

| Component | Implementation | Config |
|-----------|---------------|--------|
| CLI Entry | workflow.py → argparse | `--mode all\|main\|subagent\|rules\|warnings\|hooks\|tokens`, `--project`, `--ui` |
| tmux Launch | tmux_launcher.py | 6-Pane (main + tokens \| rules + subagent + hooks + warnings), history 50000 |
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
| Polling | monitor.py `run_streaming_loop` / `run_rules_loop` / `run_hooks_loop` / `run_tokens_loop` | 0.5s interval |
| Token Profiling | monitor.py `accumulate_tokens` / `format_tokens_block` | Cumulative output-token breakdown by block type + tool name |
| Hook Routing | monitor.py `process_hook_log` / `process_hook_log_for_display` | InstructionsLoaded → rules pane, hooks with output → hooks pane |
| Agent Tracking | monitor.py | agent_to_task, agent_to_type, buffered calls |

### Display

| Component | Implementation | Config |
|-----------|---------------|--------|
| Tool Call Formatting | formatter.py | Green (main), Blue (subagent), Red (error) |
| Subagent UI | subagent_ui.py + click_handler.py | Collapsible list, digits 1-9 toggle |
| UI Mode Loop | ui_mode.py | Screen-clear refresh, raw stdin |
| Rules Display | ui_mode.py `format_rules_block` | Pastel blue, [P]/[G] prefix, eigenes tmux Pane |
| Hooks Display | monitor.py + formatter.py | Dedicated tmux pane, format_hook_event, scrolling stream |
| Warnings Display | monitor.py + formatter.py | Dedicated tmux pane, format_unknown_type_warning |
| Token Display | monitor.py + formatter.py | Dedicated tmux pane, format_token_profile, bar chart |

### Key Files

| File | Component |
|------|-----------|
| `workflow.py` | Entry point, mode routing |
| `src/startup.py` | CLI args, signal handlers |
| `src/tmux_launcher.py` | tmux session, 5-pane layout |
| `src/monitor.py` | Core polling orchestrator |
| `src/session_finder.py` | Session discovery |
| `src/jsonl_parser.py` | JSONL parsing, tool call extraction |
| `src/hook_parser.py` | Hook log parsing |
| `src/formatter.py` | Tool call formatting |
| `src/ui_mode.py` | UI mode loop, rules formatting |
| `src/subagent_ui.py` | Subagent list rendering |
| `src/click_handler.py` | Keyboard input handling |
| `src/constants.py` | Shared constants |
| `src/utils.py` | Colors, logging, timestamps |

## Project Structure

```
Monitor_CC/
├── workflow.py                     → Pipeline entry point
├── requirements.txt
├── README.md
├── LOGS_MAP.md                     → Logging architecture reference
├── decisions/                      → Pipeline decision records (rationale per implementation choice)
│   ├── pipe01_entry_startup.md
│   ├── pipe02_data_sources.md
│   ├── pipe03_core_loop.md
│   └── pipe04_display.md
├── sources/                        → [sources.md](sources/sources.md)
├── not_working/                    → Failed approaches (markdown records)
├── repo/                           → tmux source code (external reference, own .git)
├── src/                            → [DOCS.md](src/DOCS.md)
│   ├── monitor.py
│   ├── session_finder.py
│   ├── jsonl_parser.py
│   ├── hook_parser.py
│   ├── formatter.py
│   ├── click_handler.py
│   ├── ui_mode.py
│   ├── subagent_ui.py
│   ├── tmux_launcher.py
│   ├── startup.py
│   ├── constants.py
│   ├── utils.py
│   └── logs/                       → Runtime log files (gitignored)
├── dev/                            → [DOCS.md](dev/DOCS.md)
│   └── display/                    → [DOCS.md](dev/display/DOCS.md)
│       ├── test_tmux_layout.sh
│       ├── scan_jsonl_rules.py
│       └── screenshot_panes.py     → tmux pane screenshot tool (5-pane → PNG)
```
