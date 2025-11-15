# Monitor_CC
Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output

## What's New in v1.1
- **Subagent tool call tracking**: Main agent tools display in GREEN, subagent tools in BLUE
- **Task tool highlighting**: `subagent_type` parameter highlighted in CYAN
- **Agent metadata capture**: Tracks `isSidechain` and `agentId` fields from JSONL
- **Complete visibility**: All subagent operations (Read, Grep, Bash, etc.) now visually distinguished

## Project Structure
```
Monitor_CC/
├── run.sh               # Entry point (*)
├── workflow.py          # Main orchestrator (*)
├── monitor.py           # Polling orchestrator
├── session_finder.py    # Session discovery
├── jsonl_parser.py      # JSONL parsing and extraction
├── formatter.py         # Output formatting
├── .gitignore           # Git exclusions
├── todo/                # Implementation TODOs (required)
└── debug/               # Debug scripts and tests (required)
    ├── test_malformed.py
    ├── test_todowrite.py
    └── test_edit_filter.py
```

**Note:** Complies with CLAUDE.MD Level 1: PROJECT architecture (mandatory todo/ and debug/ folders).

## workflow.py
**Purpose:** Main entry point. Sets up signal handlers and starts monitoring loop.
**Input:** None
**Output:** Console output stream

### main()
Orchestrates the entire monitoring workflow. Sets up signal handlers for graceful shutdown, prints startup message, and launches the monitor loop.

### setup_signal_handlers()
Registers SIGINT and SIGTERM handlers to enable clean shutdown with Ctrl+C.

### handle_shutdown()
Handles shutdown signals by printing a shutdown message and exiting cleanly.

### print_startup_message()
Displays the green-colored startup banner and monitoring status information.

### print_shutdown_message()
Displays the green-colored shutdown message when monitoring stops.

## monitor.py
**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls.
**Input:** None (reads from ~/.claude/projects)
**Output:** Formatted tool calls to console

### run_monitor()
Main monitoring loop that runs continuously. Initializes file positions at EOF and polls for changes every 0.5 seconds.

### initialize_file_positions()
Discovers all active session files and sets their initial read positions to EOF to avoid showing historical data.

### monitor_sessions()
Checks for new or removed sessions, updates tracking, and processes all active session files.

### update_session_tracking()
Compares current sessions with tracked sessions and adds new files to the tracking dictionary.

### process_all_sessions()
Iterates through all tracked session files and processes each one for new tool calls.

### process_session_file()
Reads new content from a single session file, parses tool calls, updates the file position, and displays formatted output.

### display_tool_call()
Formats a tool call using the formatter module and prints it to console with proper spacing.

### get_file_end_position()
Returns the file size in bytes for initializing the read position at end of file.

## session_finder.py
**Purpose:** Discovers active Claude Code session files in ~/.claude/projects.
**Input:** ~/.claude/projects directory
**Output:** List of JSONL file paths

### find_active_sessions()
Orchestrates session discovery by getting project directories, collecting JSONL files, and sorting by modification time.

### get_project_directories()
Returns all subdirectories in ~/.claude/projects where session files are stored.

### collect_jsonl_files()
Searches all project directories and collects paths to all JSONL files (main sessions and agent threads).

### sort_by_modification_time()
Sorts file paths by modification time in descending order to prioritize recently active sessions.

### is_modified_since()
Checks if a file has been modified since a given timestamp by comparing modification times.

### get_modification_time()
Returns the current modification timestamp of a file.

## jsonl_parser.py
**Purpose:** Parses JSONL conversation files and extracts correlated tool_use/tool_result pairs.
**Input:** JSONL file path and last read position
**Output:** List of tool call dictionaries with full I/O data

### parse_new_tool_calls()
Orchestrates parsing by reading new lines from file position, parsing them as JSON, extracting tool calls, and returning both results and new position.

### read_new_lines()
Seeks to the last read position and reads all new content, splitting into individual lines.

### get_current_position()
Returns the current file size to track where the next read should start.

### parse_jsonl_lines()
Attempts to parse each line as JSON, skipping malformed lines and returning list of message objects.

### extract_tool_calls()
Processes messages to find tool_use and tool_result pairs. Maintains a cache to correlate requests with responses via tool_use_id.

### get_message_content()
Extracts the content array from a message object, handling different message structures.

### is_tool_use()
Checks if a content block represents a tool invocation by examining its type field.

### is_tool_result()
Checks if a content block represents a tool result by examining its type field.

### create_tool_use_entry()
Builds a tool call dictionary from a tool_use content block, extracting name, input parameters, ID, timestamp, and agent metadata (isSidechain, agentId).

### extract_result_content()
Extracts the actual output text from a tool_result content block, handling both simple strings and complex structured responses.

## formatter.py
**Purpose:** Formats tool calls with color-coded headers (green for main agent, blue for subagents) and proper indentation.
**Input:** Tool call data (name, input, output, timestamp, ID, agent metadata)
**Output:** Formatted string with ANSI color codes

### format_tool_call()
Orchestrates formatting by creating both REQUEST and RESPONSE sections with agent-specific coloring and combining them with spacing.

### format_request()
Creates the REQUEST header with color based on agent type (green for main, blue for subagent), timestamp, tool name, and formatted input parameters. Applies special formatting for Task and TodoWrite tools.

### format_response()
Creates the RESPONSE header with color based on agent type (green for main, blue for subagent), timestamp, tool name, and formatted output content.

### format_timestamp()
Converts ISO 8601 timestamp to HH:MM:SS format for compact display.

### format_parameters()
Formats input parameters dictionary with 2-space indentation, one parameter per line.

### format_task_parameters()
Formats Task tool parameters with special highlighting for subagent_type field in cyan color.

### format_output()
Formats output content with 2-space indentation, preserving line breaks.

### format_value()
Handles different value types (strings, dicts, lists), preserving newlines for multiline strings.


## Debug Scripts

The `debug/` folder contains test scripts for development and verification:

### test_malformed.py
Tests malformed JSON line detection and warning display. Creates temporary JSONL file with invalid entries and verifies parser correctly identifies and formats warnings.

**Tests:**
- JSON syntax errors
- Unterminated strings
- Invalid characters
- Yellow warning output

**Run:** `python3 debug/test_malformed.py`

### test_todowrite.py
Tests TodoWrite special formatting with colored status icons. Validates green/yellow/white color coding and structured output.

**Tests:**
- Status icon mapping (✓/⟳/○)
- Color application (GREEN/YELLOW/RESET)
- Multi-todo formatting
- Request/response pairing

**Run:** `python3 debug/test_todowrite.py`

### test_edit_filter.py
Verifies Edit tool filtering. Confirms Edit tools are excluded from monitor output while other tools remain visible.

**Tests:**
- Edit tool exclusion count
- Other tools preserved
- Filter function behavior
- Tool breakdown statistics

**Run:** `python3 debug/test_edit_filter.py`

## Usage

### Live Monitoring (Real-time)
Start the monitor in a separate terminal window:
```bash
./Monitor_CC/run.sh
```

The monitor will:
- Auto-discover all active Claude Code sessions
- Show NEW tool calls as they happen (starts at EOF)
- Display with colored headers, timestamps, full I/O
- Continue until Ctrl+C

### Viewing Historical Sessions
To see tool calls from a completed session, modify the file path in a custom script or use the JSONL files directly at:
```
~/.claude/projects/<encoded-dir>/*.jsonl
```

## Output Format

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
```
[HH:MM:SS] REQUEST #10 → Task                                 [GREEN]
  subagent_type: Plan                                          [CYAN]
  description: Investigate subagent tracking
  prompt: Analyze the Monitor_CC codebase...

[HH:MM:SS] RESPONSE #10 ← Task                                [GREEN]
  Perfect! Now I have a comprehensive understanding...
```

### TodoWrite (Enhanced Formatting)
```
[HH:MM:SS] REQUEST #12 → TodoWrite

  TODO #1 - COMPLETED ✓
    Add format_warning() function to formatter.py          [GREEN]

  TODO #2 - IN PROGRESS ⟳
    Update parse_jsonl_lines() to track malformed lines    [YELLOW]

  TODO #3 - PENDING ○
    Test with malformed JSONL data                         [WHITE]

[HH:MM:SS] RESPONSE #12 ← TodoWrite
  Todos have been modified successfully.
```

### Malformed JSON Warnings
```
[HH:MM:SS] ⚠ WARNING - Malformed JSON                     [YELLOW]
  File: agent-629b31dd.jsonl
  Line: 47
  Error: Unterminated string starting at: line 1 column 18 (char 17)
  Content: {"type": "user", "broken json here without...
```

## What Gets Captured

**YES - Tool Operations:**
- All tool names (Task, Bash, Read, Write, Grep, Glob, WebSearch, WebFetch, AskUserQuestion, TodoWrite, etc.)
- Complete input parameters
- Complete output/results
- Timestamps
- Request-response correlation
- **Agent metadata** (isSidechain, agentId from JSONL)
- **Subagent tool calls** from agent-*.jsonl files (displayed in BLUE)

**NO - Filtered Out:**
- Edit tools (redundant to Claude Code UI)
- User prompts
- Claude thinking
- Claude text responses

## Technical Details

**Data Source:** `~/.claude/projects/<encoded-dir>/<session-id>.jsonl` and `agent-*.jsonl`
**Format:** JSONL (JSON Lines) - one message per line
**Polling:** 0.5 second interval (like Monitor_CD)
**Correlation:** Via `tool_use_id` field matching
**Filtering:** Edit tools excluded via `filter_excluded_tools()`

**Color Scheme:**
- Main agent tools: GREEN (`\033[38;5;35m`)
- Subagent tools: BLUE (`\033[38;5;33m`)
- subagent_type highlight: CYAN (`\033[38;5;51m`)
- Warnings: YELLOW (`\033[38;5;220m`)

**Agent Tracking:**
- Detects `isSidechain: true` for subagent tools
- Captures `agentId` from agent thread messages
- Processes both main session and agent-*.jsonl files

## Installation

No installation needed - works with standard Python 3.

**Requirements:**
- Python 3.6+
- Claude Code CLI installed
- Active or completed Claude Code sessions

**Quick Start:**
```bash
git clone <repo-url> Monitor_CC
cd Monitor_CC
./run.sh
```

