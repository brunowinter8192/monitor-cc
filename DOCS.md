# Monitor_CC
Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output

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
Reads new content from a single session file, parses tool calls, updates the file position, and displays formatted output. Handles Task tool requests and responses specially to track subagent spawning and buffer subagent calls until the parent Task response arrives.

### display_warning()
Logs and displays malformed JSONL warnings to the console. Formats the warning with file path, line number, error message, and truncated raw line content using yellow color coding.

### display_tool_call()
Formats a tool call using the formatter module and prints it to console with proper spacing. Applies color coding based on whether the call is from main agent or subagent.

### get_file_end_position()
Returns the file size in bytes for initializing the read position at end of file.

### is_task_request()
Checks if a tool call is a Task REQUEST by verifying the tool name is 'Task' and output is None.

### is_task_response()
Checks if a tool call is a Task RESPONSE by verifying the tool name is 'Task' and output is not None.

### is_subagent_call()
Checks if a tool call originated from a subagent by examining the is_subagent flag.

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

### filter_excluded_tools()
Filters out excluded tools from the tool calls list. Currently removes Edit tools to prevent redundant output since Edit operations are already visible in the Claude Code UI.

### sort_by_timestamp()
Sorts tool calls chronologically by their request timestamp to ensure display order matches actual execution sequence rather than response arrival order.

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

### format_warning()
Formats malformed JSONL warnings with yellow header and indented details showing file path, line number, error message, and truncated raw content.

### format_todo_list()
Applies special formatting to TodoWrite tool calls with colored status labels and icons for each todo item. Uses green for completed, yellow for in-progress, and white for pending items.

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

### truncate_line()
Truncates a line to a maximum length and appends ellipsis if truncation occurs, used for displaying long malformed JSON lines.

### get_status_icon()
Returns the appropriate icon character for a todo status (checkmark, refresh, or circle).

### get_status_color()
Returns the appropriate ANSI color code for a todo status (green, yellow, or default).

