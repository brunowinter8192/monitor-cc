# Monitor_CC Source Modules
Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output

## Module Structure
```
src/
├── __init__.py          # Package marker
├── monitor.py           # Polling orchestrator
├── session_finder.py    # Session discovery
├── jsonl_parser.py      # JSONL parsing and extraction
├── hook_parser.py       # Hook log parsing
├── formatter.py         # Output formatting
├── subagent_ui.py       # Collapsible subagent list UI
├── click_handler.py     # Keyboard input handling for UI toggle
├── DOCS.md              # This file
├── debug/               # Debug scripts and tests
└── logs/                # Module log files
```

**Note:** Entry point workflow.py resides at project root and imports from this src/ package.

## monitor.py
**Purpose:** Core polling orchestrator. Continuously monitors session files and displays new tool calls.
**Input:** Optional project path filter, mode filter, and UI mode flag (reads from ~/.claude/projects)
**Output:** Formatted tool calls to console or collapsible UI list

### run_monitor()
Main monitoring loop that runs continuously. Accepts optional project filter, mode, and UI flag parameters, stores them globally, initializes file positions at EOF, and chooses between streaming display or UI mode. In UI mode with subagent filter, renders collapsible subagent list instead of streaming output.

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
Formats a tool call using the formatter module and prints it to console with proper spacing. Applies color coding based on whether the call is from main agent or subagent. Checks for pending PreToolUse hook entries and attaches them as hook annotations below the REQUEST header if found.

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

### run_streaming_loop()
Executes the traditional continuous polling and streaming display loop. Processes hook log first, then monitors sessions every 0.5 seconds and displays tool calls as they arrive. Used when UI mode is disabled.

### process_hook_log()
Reads new entries from the hook log file, filters by project if a filter is active, and processes each entry. UserPromptSubmit entries are displayed immediately as USER PROMPT stamps. PreToolUse entries are cached for later attachment to their corresponding tool calls.

### display_user_prompt_entry()
Displays a USER PROMPT stamp in pastel purple color. Includes any hook output below the stamp if present. Called when a UserPromptSubmit hook entry is processed.

### run_ui_loop()
Executes the UI mode polling loop with collapsible subagent list rendering. Sets up mouse tracking at start, then monitors sessions every 0.5 seconds, handles pending mouse clicks, updates subagent metadata, and syncs the formatted UI to screen with clear-and-redraw. Restores terminal settings on exit via finally block.

### handle_pending_clicks()
Checks for and processes any pending mouse click events. Reads mouse data from stdin, parses the SGR escape sequence, determines if click is on a toggle area, and calls toggle_subagent_state if valid agent found at clicked line.

### track_subagent_metadata()
Builds and maintains metadata for each subagent from parsed tool calls. Creates new metadata entries when agents are first discovered, tracking agent name, timestamp, file, parent task ID, and call count. Updates call count as new calls arrive.

### update_tool_calls_by_agent()
Groups tool calls by agent ID for UI rendering. Initializes empty list for new agents and appends calls to existing agent lists.

### sync_ui_to_screen()
Renders the collapsible subagent list and displays it to terminal. Clears the screen with ANSI escape codes and prints the formatted UI output from the subagent_ui module.

### extract_subagent_type()
Retrieves the subagent_type parameter from the parent Task tool call. Searches through tool use caches to find the Task request that spawned this agent and extracts the subagent_type from its input parameters.

### format_warning()
Formats malformed JSONL warnings with yellow header and indented details showing file path, line number, error message, and truncated raw content for display to console.

### truncate_line()
Truncates a line to a maximum length and appends ellipsis if truncation occurs, used for displaying long malformed JSON lines in warnings.

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
Attempts to parse each line as JSON, tracking malformed lines with their error details and returning both the list of successfully parsed message objects and the list of malformed line information.

### extract_tool_calls()
Processes messages to find tool_use and tool_result pairs. Maintains a cache to correlate requests with responses via tool_use_id.

### build_malformed_warnings()
Builds warning dictionaries from malformed line data by mapping file path, line number, error message, and raw line content into structured warning objects.

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

### extract_system_reminders()
Extracts all system-reminder tags from a content string using regex pattern matching. Returns a list of reminder contents with tags stripped and whitespace trimmed.

### strip_system_reminders()
Removes all system-reminder tags from a content string. Returns the cleaned content for display without embedded reminders.

### filter_excluded_tools()
Filters out excluded tools from the tool calls list. Currently removes Edit tools to prevent redundant output since Edit operations are already visible in the Claude Code UI.

### sort_by_timestamp()
Sorts tool calls chronologically by their request timestamp to ensure display order matches actual execution sequence rather than response arrival order.

## hook_parser.py
**Purpose:** Parses hook log file (hook_outputs.jsonl) written by Claude Code hooks for display in monitor.
**Input:** Hook log file path and last read position
**Output:** List of hook entry dictionaries with timestamp, cwd, hook_event, hook_script, output, and tool_name

### parse_new_hook_entries()
Orchestrates parsing by reading new lines from hook log file, parsing them as JSON, and returning entries with new position. Similar pattern to jsonl_parser.

### read_new_lines()
Seeks to the last read position in hook log file and reads all new content, splitting into individual lines.

### get_current_position()
Returns the current file size to track where the next read should start.

### parse_lines()
Attempts to parse each line as JSON, logging errors for malformed lines. Returns list of parsed entry dictionaries.

### filter_by_project()
Filters hook entries by comparing their cwd field to the project filter path. Returns only entries matching the current project filter.

## formatter.py
**Purpose:** Formats tool calls with color-coded headers (green for main agent, blue for subagents) and proper indentation.
**Input:** Tool call data (name, input, output, timestamp, ID, agent metadata)
**Output:** Formatted string with ANSI color codes

### format_tool_call()
Orchestrates formatting by creating both REQUEST and RESPONSE sections with agent-specific coloring and combining them with spacing.

### combine_request_response()
Combines the formatted request and response sections into a single output string with proper line spacing between them.

### format_request()
Creates the REQUEST header with color based on agent type (green for main, blue for subagent), timestamp, tool name, and formatted input parameters. Applies special formatting for Task and TodoWrite tools.

### format_response()
Creates the RESPONSE header with color based on agent type (green for main, blue for subagent), timestamp, tool name, and formatted output content.

### format_todo_list()
Applies special formatting to TodoWrite tool calls with colored status labels and icons for each todo item. Uses green for completed, yellow for in-progress, and white for pending items.

### format_timestamp()
Converts ISO 8601 timestamp (UTC) to local timezone HH:MM:SS format for compact display.

### format_parameters()
Formats input parameters dictionary with 2-space indentation, one parameter per line.

### format_task_parameters()
Formats Task tool parameters with special highlighting for subagent_type field in cyan color.

### format_output()
Formats output content with 2-space indentation, preserving line breaks. Detects long outputs (>=10k chars), logs them to src/logs/10_long_outputs.log via log_long_output(), and applies light red background color for visual distinction.

### format_system_reminders()
Formats system reminder messages with pastel blue color. Processes each reminder, splits by newlines, and applies indentation and color to non-empty lines.

### format_value()
Handles different value types (strings, dicts, lists), preserving newlines for multiline strings.

### get_status_icon()
Returns the appropriate icon character for a todo status (checkmark, refresh, or circle).

### get_status_color()
Returns the appropriate ANSI color code for a todo status (green, yellow, or default).

### log_long_output()
Logs long tool outputs (>=10k chars) to src/logs/10_long_outputs.log with character count, line count, preview of first 500 chars, full content, and separator line for debugging purposes.

### format_user_prompt()
Formats USER PROMPT stamp in pastel purple color. Accepts optional list of hook outputs to display below the stamp. Used when UserPromptSubmit hooks are processed.

### format_hook_annotation()
Formats a PreToolUse hook annotation line in pastel purple. Shows hook script name and output message. Used to attach hook information to tool call display.

## subagent_ui.py
**Purpose:** Renders collapsible subagent list UI for interactive monitoring of subagent activity.
**Input:** Subagent metadata dictionaries and grouped tool calls by agent ID
**Output:** Formatted terminal UI string with collapsible entries

### render_subagent_list()
Orchestrates UI rendering by building header, entries, and footer sections. Combines all sections with proper spacing to create the complete collapsible list display.

### build_list_header()
Creates the UI header showing total count of active subagents. Uses cyan color for visual distinction from content.

### build_all_entries()
Iterates through all subagents and builds either collapsed or expanded entries based on current state. Returns yellow message if no subagents are active yet. Sorts entries chronologically by timestamp.

### build_collapsed_entry()
Formats a collapsed subagent entry showing index number, plus icon, agent name, agent ID, and timestamp. Uses blue color for subagent identification consistent with main monitor coloring.

### build_expanded_entry()
Formats an expanded entry with collapsed header modified to minus icon plus indented list of all tool calls for that agent. Shows yellow message if agent has no tool calls yet.

### format_subagent_name()
Generates unique display names for subagents. Uses subagent_type if available, otherwise falls back to agent_id. Appends timestamp suffix if name already exists to handle multiple instances of same agent type.

### format_tool_call_summary()
Creates a single-line summary of a tool call showing timestamp, bidirectional arrow if response received, call number, tool name, and input preview. Uses green color consistent with main agent formatting.

### combine_sections()
Joins header and entry list with proper newline spacing to create final formatted output string.

### get_agent_display_name()
Extracts readable name from subagent_type parameter or falls back to agent_id. Converts hyphenated names to title case for better readability.

### extract_timestamp_from_agent()
Retrieves the creation timestamp for a subagent by examining the first tool call in its list. Returns current time if no calls exist yet.

### count_calls_for_agent()
Returns the total number of tool calls executed by a specific agent. Simple length check on the tool calls list.

### format_timestamp()
Converts ISO 8601 timestamp from UTC to local timezone in HH:MM:SS format. Handles invalid timestamps gracefully by returning zeros.

### get_input_preview()
Extracts a preview showing ALL parameters from tool call input. Returns key=value pairs for each parameter, truncating individual values over 50 chars and total output over 120 chars. Includes defensive checks for None or non-dict inputs, returning appropriate fallback strings.

### toggle_subagent_state()
Toggles the expanded/collapsed state for a given agent ID. Flips the boolean value in subagent_states dictionary and logs the state change. Returns True if agent exists and was toggled, False otherwise.

## click_handler.py
**Purpose:** Handles keyboard input for the collapsible subagent UI. Reads digit keypresses (1-9) to toggle subagent expanded/collapsed state.
**Input:** Single character keypresses from stdin in raw mode
**Output:** Agent ID to toggle when digit key pressed

### setup_keyboard_input()
Orchestrates keyboard input initialization by setting stdin to raw mode. Returns True on success, False on failure. Called once when UI loop starts.

### set_raw_stdin()
Configures stdin to cbreak mode using termios to receive individual characters without line buffering. Stores original terminal settings for later restoration. Returns True on success, False on failure.

### restore_terminal()
Restores original terminal settings saved during setup. Called in finally block when UI loop exits to ensure terminal is always restored.

### read_keypress()
Checks stdin for available data without blocking using select. Returns single character if available, None otherwise. Called each UI loop iteration.

### parse_digit_key()
Checks if character is a digit 1-9. Returns integer index if valid digit, None otherwise.

### get_agent_by_index()
Looks up agent ID by numeric index (1-based) from sorted subagent metadata. Agents are sorted by timestamp so index 1 is the oldest agent. Returns agent ID or None if index out of bounds.

