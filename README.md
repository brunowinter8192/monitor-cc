# Monitor_CC
Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output

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

Start the monitor in a separate terminal window:
```bash
# Monitor ALL active Claude Code sessions
./Monitor_CC/run.sh

# Monitor specific project only
./Monitor_CC/run.sh /path/to/your/project
```

**Example:** Monitor only the Meta/blank project:
```bash
./run.sh /path/to/project
```

The monitor will:
- Auto-discover active Claude Code sessions (all or filtered by project)
- Show NEW tool calls as they happen (starts at EOF)
- Display with colored headers, timestamps, full I/O
- Continue until Ctrl+C

### Viewing Historical Sessions
To see tool calls from a completed session, the JSONL files are located at:
```
~/.claude/projects/<encoded-dir>/*.jsonl
```

## Output Format

The monitor displays all tool calls with color-coded formatting to distinguish main agent operations from subagent operations.

### Main Agent Tool Calls (GREEN)
```
[HH:MM:SS] REQUEST #1 → Bash                                  [GREEN]
  command: ls -la /Users/bruno/project
  description: List project files

[HH:MM:SS] RESPONSE #1 ← Bash                                 [GREEN]
  total 88
  drwxr-xr-x  5 bruno  staff  160 Nov 14 22:30 .
  -rw-r--r--  1 bruno  staff  123 Nov 14 22:28 file.py
```

### Subagent Tool Calls (BLUE)
Subagent operations are automatically detected from agent thread files and displayed in blue:
```
[HH:MM:SS] REQUEST #15 → Read                                 [BLUE]
  file_path: /Users/bruno/project/monitor.py

[HH:MM:SS] RESPONSE #15 ← Read                                [BLUE]
  # INFRASTRUCTURE
  import time
  from pathlib import Path
  ...
```

### Task Tool with Highlighted subagent_type
The subagent_type parameter is highlighted in cyan for quick identification:
```
[HH:MM:SS] REQUEST #10 → Task                                 [GREEN]
  subagent_type: Plan                                          [CYAN]
  description: Investigate subagent tracking
  prompt: Analyze the Monitor_CC codebase...

[HH:MM:SS] RESPONSE #10 ← Task                                [GREEN]
  Perfect! Now I have a comprehensive understanding...
```

### TodoWrite (Enhanced Formatting)
TodoWrite tools receive special formatting with status icons and color-coded states:
```
[HH:MM:SS] REQUEST #12 → TodoWrite

  TODO #1 - COMPLETED [CHECKMARK]
    Add format_warning() function to formatter.py          [GREEN]

  TODO #2 - IN PROGRESS [REFRESH]
    Update parse_jsonl_lines() to track malformed lines    [YELLOW]

  TODO #3 - PENDING [CIRCLE]
    Test with malformed JSONL data                         [WHITE]

[HH:MM:SS] RESPONSE #12 ← TodoWrite
  Todos have been modified successfully.
```

### Malformed JSON Warnings
Invalid JSONL entries are detected and displayed with yellow warning formatting:
```
[HH:MM:SS] [WARNING] Malformed JSON                       [YELLOW]
  File: agent-629b31dd.jsonl
  Line: 47
  Error: Unterminated string starting at: line 1 column 18 (char 17)
  Content: {"type": "user", "broken json here without...
```

## What Gets Captured

### YES - Tool Operations
- **All tool names:** Task, Bash, Read, Write, Grep, Glob, WebSearch, WebFetch, AskUserQuestion, TodoWrite, etc.
- **Complete input parameters:** All arguments passed to tools
- **Complete output/results:** Full tool responses
- **Timestamps:** HH:MM:SS format for each request/response
- **Request-response correlation:** Matched via tool_use_id
- **Agent metadata:** isSidechain flag and agentId from JSONL
- **Subagent tool calls:** Operations from agent-*.jsonl files (displayed in BLUE)

### NO - Filtered Out
- **Edit tools:** Excluded as redundant to Claude Code UI
- **User prompts:** Not displayed
- **Claude thinking:** Internal reasoning not shown
- **Claude text responses:** Conversational replies filtered out

The filtering ensures the monitor focuses exclusively on tool operations and their I/O, providing a clean view of what actions are being performed.

## Technical Details

### Data Source
- **Main sessions:** `~/.claude/projects/<encoded-dir>/<session-id>.jsonl`
- **Subagent threads:** `~/.claude/projects/<encoded-dir>/agent-*.jsonl`
- **Format:** JSONL (JSON Lines) - one message per line

### Polling Mechanism
- **Interval:** 0.5 seconds (similar to Monitor_CD)
- **Position tracking:** Maintains file offset per session to read only new content
- **Position initialization:** Main session files start at EOF (new activity only), subagent files start at beginning (complete history)
- **Session discovery:** Scans project directories on each poll to detect new sessions
- **Project filtering:** Optional CLI argument filters sessions by project path (decodes directory names like `-Users-bruno-project` → `/Users/bruno/project`)

### Correlation Mechanism
Tool calls are correlated by matching tool_use_id fields:
1. Parse tool_use content blocks (requests) and cache by ID
2. Parse tool_result content blocks (responses) and match to cached requests
3. Combine matched pairs into complete tool call entries
4. Display with synchronized REQUEST/RESPONSE formatting

### Filtering Logic
The `filter_excluded_tools()` function removes Edit tools from the output stream while preserving all other tool types.

### Color Scheme
- **Main agent tools:** GREEN (`\033[38;5;35m`)
- **Subagent tools:** BLUE (`\033[38;5;33m`)
- **subagent_type highlight:** CYAN (`\033[38;5;51m`)
- **Warnings:** YELLOW (`\033[38;5;220m`)
- **TodoWrite status icons:**
  - Completed: [CHECKMARK] (GREEN)
  - In Progress: [REFRESH] (YELLOW)
  - Pending: [CIRCLE] (WHITE)

### Agent Tracking
The monitor detects subagent operations through JSONL metadata:
- **isSidechain flag:** Identifies tool calls from subagent contexts
- **agentId field:** Captures specific agent thread identifier
- **File pattern:** Processes both main session and agent-*.jsonl files
- **Color coding:** Automatically applies BLUE formatting to subagent tools

### Logging
Internal events and errors are logged to logs/ directory with timestamp, level, and message format.

## Installation

No installation needed - works with standard Python 3.

### Requirements
- Python 3.6+
- Claude Code CLI installed
- Active or completed Claude Code sessions

### Setup
```bash
git clone <repo-url> Monitor_CC
cd Monitor_CC
./run.sh
```

## Debug & Testing

The `debug/` folder contains verification scripts:

- **test_malformed.py** - Tests malformed JSON detection and warning display
- **test_todowrite.py** - Validates TodoWrite formatting with colored status icons
- **test_edit_filter.py** - Verifies Edit tool filtering logic

Run tests individually:
```bash
python3 debug/test_malformed.py
python3 debug/test_todowrite.py
python3 debug/test_edit_filter.py
```

## Architecture Documentation

For complete module architecture, function descriptions, and implementation details, see [DOCS.md](DOCS.md).
