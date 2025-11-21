# Monitor_CC
Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output

**Remote:** https://github.com/brunowinter8192/ClaudeCode-Monitor

After major changes, push to remote:
```bash
git add -A && git commit -m "Your message" && git push
```

## What It Does

Monitor_CC is a real-time monitoring system for Claude Code CLI sessions. It provides complete visibility into all tool operations by continuously polling Claude Code's internal JSONL conversation files.

The workflow operates as follows:

1. **Auto-discovers** all active Claude Code sessions in `~/.claude/projects`
2. **Initializes** file read positions at EOF to show only new activity
3. **Polls** session files every 0.5 seconds for new content
4. **Parses** JSONL message format and extracts tool_use/tool_result pairs
5. **Correlates** requests with responses via tool_use_id matching
6. **Formats** output with color-coded headers distinguishing main agent vs subagent tools
7. **Displays** complete tool I/O to console with timestamps and proper indentation

The monitor tracks both main session files and subagent thread files (agent-*.jsonl), automatically detecting and color-coding subagent operations based on isSidechain metadata.

## Quick Start

Start the monitor (opens tmux split-screen automatically):
```bash
# Monitor ALL active Claude Code sessions (tmux split-screen)
python3 workflow.py

# Monitor specific project only
python3 workflow.py --project /path/to/your/project
```

**Example:** Monitor only the Meta/blank project:
```bash
python3 workflow.py --project /path/to/project
```

The monitor will:
- Open tmux with split-screen (Main Agent left, Subagent right)
- Auto-discover active Claude Code sessions (all or filtered by project)
- Show NEW tool calls as they happen (starts at EOF)
- Display with colored headers, timestamps, full I/O
- Continue until Ctrl+C

### Monitor Modes

By default, the monitor opens a tmux split-screen. You can also run single modes:
```bash
# Default: Split-screen (requires tmux)
python3 workflow.py

# Split-screen with collapsible UI for subagents
python3 workflow.py --ui

# Main agent only (no tmux)
python3 workflow.py --mode main

# Subagent only with streaming display (no tmux)
python3 workflow.py --mode subagent

# Subagent only with collapsible UI (no tmux)
python3 workflow.py --mode subagent --ui
```

**Collapsible UI Mode:**
When enabled with `--ui` flag, the right pane displays a collapsible list of active subagents instead of streaming their tool calls. Each subagent appears as a numbered entry showing its name, filename, call count, and timestamp. Entries can be expanded to view detailed tool calls or kept collapsed for a compact overview.

### tmux Controls

- `Ctrl+C` - Stop the monitor
- `Ctrl+B` then `D` - Detach from tmux (monitor continues running)
- `tmux ls` - List running monitor sessions (names are `monitor_cc_<hash>`)
- `tmux attach -t <session-name>` - Reattach to running monitor
- `Ctrl+B` then arrow keys - Resize panes

### Viewing Historical Sessions
To see tool calls from a completed session, the JSONL files are located at:
```
~/.claude/projects/<encoded-dir>/*.jsonl
```

## What's Important About This Project

This project has unique debugging challenges:
- **Tmux-based:** Runs in split-screen, difficult to debug interactively
- **Production-only testing:** Cannot easily test without real execution
- **Agent debugging:** Agents debug EXCLUSIVELY through logs (no monitor access)
- **User feedback loop:** User must execute and provide log feedback for debugging

**Result:** Comprehensive logging is CRITICAL - every function with meaningful operations logs extensively.

---

## Debugging Philosophy & Logging System

### Why Comprehensive Logging?

Traditional debugging tools (debuggers, interactive monitors) are unavailable because:
- Code runs in tmux split-screen
- Agents cannot attach debuggers or view UI
- Production execution cannot be easily replicated

**Solution:** Treat logs as the PRIMARY debugging interface. Every function with meaningful state changes, decisions, or data processing MUST log.

### Logging Architecture

#### Multi-File Strategy
Each module/concern gets dedicated log file(s) for focused debugging:
- **No noise** from unrelated operations
- **Fast diagnosis** - only read relevant logs
- **Example:** monitor.py uses 4 separate loggers (startup, clicks, UI, sessions)

#### All Logs on INFO Level
- Agents cannot change log configuration
- DEBUG level would be invisible to agents
- **Every operation** must be visible → INFO for everything
- Use `logging.warning()` for recoverable issues, `logging.error()` for exceptions

### Mandatory Logging Points

Every function MUST log if it performs ANY of these:

**1. Orchestrator Entry/Exit**
```python
def process_workflow(input_file, output_dir):
    logging.info(f"process_workflow: input={input_file}, output={output_dir}")
    result = do_processing()
    logging.info(f"process_workflow completed: records={len(result)}")
    return result
```

**2. State Changes**
```python
for removed_file in removed_files:
    logging.info(f"Session removed: {removed_file}")
    del file_positions[removed_file]
```

**3. Control Flow Decisions**
```python
if tool_use_id in cache:
    logging.info(f"Matched tool_result: id={tool_use_id}, tool={tool_name}")
else:
    logging.info(f"Orphaned tool_result: id={tool_use_id}")
```

**4. Data Processing Statistics**
```python
malformed_pct = malformed / (total or 1) * 100
logging.info(f"Parsed: valid={valid}, malformed={malformed} ({malformed_pct:.1f}%)")
```

**5. Categorization Breakdowns** (CRITICAL for this project)
```python
logging.info(f"Processed {file}: task_req={n1}, task_resp={n2}, subagent_ui={n3}, buffered={n4}, displayed={n5}")
```

**6. Tool-Use Pairing** (CRITICAL for orphaned results)
```python
logging.info(f"Cached tool_use: id={tool_use_id}, tool={tool_name}")
logging.info(f"Matched tool_result: id={tool_use_id}")
logging.info(f"Orphaned tool_result: id={tool_use_id} (no matching tool_use)")
```

**7. Loop Summaries** (NOT every iteration)
```python
if iteration % 20 == 0:  # Every 10 seconds
    logging.info(f"monitor_sessions: iteration={iteration}, tracking={len(file_positions)}")
```

### Critical Log Files for Agent Debugging

When agents encounter bugs, they check these logs:

| Issue | Primary Logs | What to Look For |
|-------|-------------|------------------|
| **Subagent not expanding** | monitor_clicks.log, subagent_ui.log | Mouse coords, line calculation, toggle state |
| **Tool calls missing** | monitor_sessions.log, jsonl_parser.log | Categorization breakdown, orphaned results |
| **Session not found** | session_finder.log, monitor_startup.log | Filter matching, session discovery |
| **JSONL parsing errors** | jsonl_parser.log | Malformed lines, parse statistics |
| **Split-screen not starting** | workflow.log | Tmux commands, FIFO setup |
| **Filter not working** | session_finder.log | encode_project_path, matches_project_filter |

### Example: Debugging "Tool Calls Not Displaying"

**Step 1:** Check **monitor_sessions.log** for categorization:
```
Processed session.jsonl: task_req=5, task_resp=3, subagent_ui=10, subagent_displayed=0, subagent_buffered=7
```
→ See that subagent calls are being buffered, not displayed

**Step 2:** Check **jsonl_parser.log** for pairing issues:
```
Cached tool_use: id=tool_123, tool=Task
Orphaned tool_result: id=tool_456 (no matching tool_use in cache)
```
→ Orphaned results indicate pairing problem

**Step 3:** Cross-reference with **monitor_ui.log**:
```
render_subagent_list: 3 agents, 0 expanded
Built 3 entries (0 expanded)
```
→ Agents exist but aren't expanded

**Resolution:** Check toggle logic in monitor_clicks.log

### Logging Setup Patterns

**Single Logger (most modules):**
```python
# INFRASTRUCTURE
import logging

logging.basicConfig(
    filename='src/logs/module_name.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

**Multiple Loggers (distinct concerns):**
```python
# INFRASTRUCTURE
import logging

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_clicks = logging.getLogger('monitor.clicks')
handler = logging.FileHandler('src/logs/monitor_clicks.log')
handler.setFormatter(log_format)
logger_clicks.addHandler(handler)
logger_clicks.setLevel(logging.INFO)
```

---


