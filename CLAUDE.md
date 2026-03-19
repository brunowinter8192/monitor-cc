# Monitor_CC

Real-time Claude Code session monitor with TUI dashboard.

## Sources

| Source | URL | Relevance |
|--------|-----|-----------|
| tmux man page | github.com/tmux/tmux | split-window, pane targeting, layout |
| Claude Code #30973 | github.com/anthropics/claude-code/issues/30973 | InstructionsLoaded hook behavior |
| Claude Code #33275 | github.com/anthropics/claude-code/issues/33275 | InstructionsLoaded session_start bug |
| Claude Code #31017 | github.com/anthropics/claude-code/issues/31017 | InstructionsLoaded /clear behavior |
| Claude Code #12151 | github.com/anthropics/claude-code/issues/12151 | Plugin hook output bug (not affecting us) |

## Pipeline Components

### Entry & Startup

| Component | Implementation | Config |
|-----------|---------------|--------|
| CLI Entry | workflow.py → argparse | `--mode all\|main\|subagent\|rules`, `--project`, `--ui` |
| tmux Launch | tmux_launcher.py | 3-Pane (main \| rules + subagent), history 50000 |
| Signal Handling | startup.py | SIGINT/SIGTERM → graceful shutdown |

### Data Sources

| Component | Implementation | Config |
|-----------|---------------|--------|
| Session Discovery | session_finder.py | `~/.claude/projects/**/*.jsonl` + `*/subagents/agent-*.jsonl` |
| JSONL Parsing | jsonl_parser.py | tool_use/tool_result pairs, user prompts, media, thinking, skills |
| Hook Parsing | hook_parser.py | `src/logs/hook_outputs.jsonl` → UserPrompt, PreTool, InstructionsLoaded |

### Core Loop

| Component | Implementation | Config |
|-----------|---------------|--------|
| Polling | monitor.py `run_streaming_loop` / `run_rules_loop` | 0.5s interval |
| Hook Routing | monitor.py `process_hook_log` | Routes 3 hook types to state dicts |
| Agent Tracking | monitor.py | agent_to_task, agent_to_type, buffered calls |
| Usage Accumulation | monitor.py `accumulate_usage` | Per-turn token totals |

### Display

| Component | Implementation | Config |
|-----------|---------------|--------|
| Tool Call Formatting | formatter.py | Green (main), Blue (subagent), Red (error) |
| Subagent UI | subagent_ui.py + click_handler.py | Collapsible list, digits 1-9 toggle |
| UI Mode Loop | ui_mode.py | Screen-clear refresh, raw stdin |
| Rules Display | ui_mode.py `format_rules_block` | Pastel blue, [P]/[G] prefix, eigenes tmux Pane |

### Key Files

| File | Component |
|------|-----------|
| `workflow.py` | Entry point, mode routing |
| `src/startup.py` | CLI args, signal handlers |
| `src/tmux_launcher.py` | tmux session, 3-pane layout |
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
├── DOCS.md                         → [Root Module Docs](DOCS.md)
├── decisions/                      → Pipeline decision records (rationale per implementation choice)
│   ├── pipe01_entry_startup.md
│   ├── pipe02_data_sources.md
│   ├── pipe03_core_loop.md
│   └── pipe04_display.md
├── sources/
├── src/
│   ├── DOCS.md                     → [Module Docs](src/DOCS.md)
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
│   └── utils.py
├── dev/                            → [DOCS.md](dev/DOCS.md)
│   └── display/                    → [DOCS.md](dev/display/DOCS.md)
│       └── test_tmux_layout.sh
```
