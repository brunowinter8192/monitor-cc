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
**Purpose:** Main entry point. Launches tmux split-screen by default or runs single monitor mode.
**Input:** Optional --project and --mode arguments from command line
**Output:** Console output stream (or tmux session with split panes)

### main()
Orchestrates the entire monitoring workflow. Parses CLI arguments to determine mode and project filter. If mode is 'all' (default), launches tmux split-screen with main and subagent monitors side-by-side. Otherwise, sets up signal handlers and runs single monitor mode.

### launch_split_screen()
Launches a tmux session with two panes: main agent monitor on left and subagent monitor on right. Checks for tmux installation and whether already running inside tmux. Creates new tmux session named 'monitor_cc' and spawns both monitor processes with appropriate --mode flags.

### is_tmux_installed()
Checks if tmux is available on the system by running 'which tmux'.

### is_inside_tmux()
Checks if the process is already running inside a tmux session by examining the TMUX environment variable.

### setup_signal_handlers()
Registers SIGINT and SIGTERM handlers to enable clean shutdown with Ctrl+C.

### handle_shutdown()
Handles shutdown signals by printing a shutdown message and exiting cleanly.

### parse_arguments()
Parses command line arguments using argparse. Accepts --project for project path filtering and --mode for agent type filtering (all, main, or subagent). Returns a Namespace object with parsed values.

### print_startup_message()
Displays the green-colored startup banner and monitoring status information. Shows which project is being monitored if a filter is active, and displays the current mode if not running in 'all' mode.

### print_shutdown_message()
Displays the green-colored shutdown message when monitoring stops.

## monitor.py
**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls.
**Input:** Optional project path filter and mode filter (reads from ~/.claude/projects)
**Output:** Formatted tool calls to console

### run_monitor()
Main monitoring loop that runs continuously. Accepts optional project filter and mode parameters, stores them globally, initializes file positions at EOF, and polls for changes every 0.5 seconds. The filters are passed through to session discovery and filtering on each poll.

### initialize_file_positions()
Discovers all active session files (filtered by project if specified) and sets their initial read positions to EOF to avoid showing historical data.

### monitor_sessions()
Checks for new or removed sessions (filtered by project if specified), applies mode filtering to select main or subagent files, updates tracking, and processes filtered session files.

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

### get_initial_position()
Determines the initial read position for a new session file. Returns 0 for subagent files to capture complete history, or EOF for main session files to show only new activity.

### is_agent_file()
Checks if a file is a subagent file by examining whether the filename starts with 'agent-'.

### filter_sessions_by_mode()
Filters the list of session files based on the mode parameter. Returns all files for 'all' mode, only main session files (non-agent) for 'main' mode, and only agent files for 'subagent' mode.

### is_task_request()
Checks if a tool call is a Task REQUEST by verifying the tool name is 'Task' and output is None.

### is_task_response()
Checks if a tool call is a Task RESPONSE by verifying the tool name is 'Task' and output is not None.

### is_subagent_call()
Checks if a tool call originated from a subagent by examining the is_subagent flag.

## session_finder.py
**Purpose:** Discovers active Claude Code session files in ~/.claude/projects with optional project filtering.
**Input:** ~/.claude/projects directory, optional project path filter
**Output:** List of JSONL file paths

### find_active_sessions()
Orchestrates session discovery by getting project directories, collecting JSONL files (optionally filtered by project path), and sorting by modification time.

### get_project_directories()
Returns all subdirectories in ~/.claude/projects where session files are stored.

### collect_jsonl_files()
Searches project directories and collects paths to JSONL files. Accepts optional project filter parameter and skips directories that do not match the filter.

### matches_project_filter()
Checks if a project directory matches the filter path by encoding the filter path to match Claude's directory naming convention and comparing it to the directory name.

### encode_project_path()
Encodes a file system path to match Claude's directory naming convention by converting slashes and underscores to hyphens. For example, `/Users/bruno/project_name` becomes `-Users-bruno-project-name`.

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
Converts ISO 8601 timestamp (UTC) to local timezone HH:MM:SS format for compact display.

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

