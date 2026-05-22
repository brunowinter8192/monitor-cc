# INFRASTRUCTURE

# Colors — Catppuccin Mocha palette (https://catppuccin.com/palette/)
# Truecolor ANSI \033[38;2;R;G;Bm (FG) / \033[48;2;R;G;Bm (BG)
# Semantic mapping:
#   text=Text, title=Mauve, title-soft=Lavender
#   error=Red, warning=Yellow, success=Green, info=Blue
#   accent=Sky, accent-warm=Peach
#   hover-bg=Surface1, zebra-bg=Surface0, error-bg=Red, stripped-bg=custom mustard
RESET = '\033[0m'
RED = '\033[38;2;243;139;168m'
GREEN = '\033[38;2;166;227;161m'
YELLOW = '\033[38;2;249;226;175m'
BLUE = '\033[38;2;137;180;250m'
CYAN = '\033[38;2;137;220;235m'
MAGENTA = '\033[38;2;245;194;231m'
WHITE = '\033[38;2;205;214;244m'
PURPLE = '\033[38;2;203;166;247m'
ORANGE = '\033[38;2;250;179;135m'
PASTEL_BLUE = '\033[38;2;116;199;236m'
PASTEL_PURPLE = '\033[38;2;180;190;254m'
LIGHT_RED_BG = '\033[48;2;243;139;168m'
PASTEL_ORANGE = '\033[38;2;242;205;205m'
PASTEL_GREEN = '\033[38;2;148;226;213m'
HOVER_BG = '\033[48;2;69;71;90m'
DIM = '\033[2m'
DIM_YELLOW_BG = '\033[48;2;94;81;47m'
COLLISION_BG = '\033[48;2;80;30;40m'
ZEBRA_BG_A = ''
ZEBRA_BG_B = '\033[48;2;49;50;68m'
SOFT_RESET = '\033[39m'
SEARCH_MATCH_BG   = '\033[48;2;62;55;0m'    # dark amber — search match row BG
SEARCH_CURRENT_BG = '\033[48;2;130;95;0m'   # warm amber — current search match row BG

# Config values
POLL_INTERVAL = 0.5
INPUT_POLL_INTERVAL = 0.05
WARNINGS_POLL_INTERVAL = 10.0
LONG_OUTPUT_THRESHOLD = 10000
TMUX_HISTORY_LIMIT = '50000'
EXPANDED_MAX_LINES = 15
PROXY_MESSAGES_KEEP_LAST = 10  # entries at end of list that retain messages for expand UX
PROXY_REPARSE_INTERVAL_SECONDS = 3600  # periodic re-init of proxy panes to release parent pymalloc pages
WORKER_COL_WIDTH = 20  # name-field width; full column = W: + name + space = 23 chars
WARNINGS_INITIAL_TAIL_BYTES = 50_000_000  # max bytes to back-seek on initial log parse to bound pymalloc peak
MAIN_EVENT_BUFFER_CAP = 1000

# Tool names
TOOL_TASK = 'Task'

# Mode names
MODE_ALL = 'all'
MODE_MAIN = 'main'
MODE_WARNINGS = 'warnings'
MODE_TOKENS = 'tokens'
MODE_WORKERS = 'workers'
MODE_PROXY = 'proxy'
MODE_METADATA = 'metadata'
MODE_WORKER_PROXY = 'worker-proxy'
MODE_WORKER_METADATA = 'worker-metadata'

# Hook events — session lifecycle
HOOK_SESSION_START = 'SessionStart'
HOOK_SESSION_END = 'SessionEnd'

# Hook events — user input
HOOK_USER_PROMPT = 'UserPromptSubmit'

# Hook events — tools
HOOK_PRE_TOOL = 'PreToolUse'
HOOK_POST_TOOL = 'PostToolUse'
HOOK_POST_TOOL_FAILURE = 'PostToolUseFailure'
HOOK_PERMISSION_REQUEST = 'PermissionRequest'
HOOK_PERMISSION_DENIED = 'PermissionDenied'

# Hook events — agents
HOOK_SUBAGENT_START = 'SubagentStart'
HOOK_SUBAGENT_STOP = 'SubagentStop'
HOOK_TEAMMATE_IDLE = 'TeammateIdle'

# Hook events — tasks
HOOK_TASK_CREATED = 'TaskCreated'
HOOK_TASK_COMPLETED = 'TaskCompleted'

# Hook events — response
HOOK_STOP = 'Stop'
HOOK_STOP_FAILURE = 'StopFailure'

# Hook events — files
HOOK_FILE_CHANGED = 'FileChanged'
HOOK_CWD_CHANGED = 'CwdChanged'
HOOK_CONFIG_CHANGE = 'ConfigChange'

# Hook events — context
HOOK_PRE_COMPACT = 'PreCompact'
HOOK_POST_COMPACT = 'PostCompact'

# Hook events — MCP
HOOK_ELICITATION = 'Elicitation'
HOOK_ELICITATION_RESULT = 'ElicitationResult'
HOOK_NOTIFICATION = 'Notification'

# Hook events — worktree
HOOK_WORKTREE_CREATE = 'WorktreeCreate'
HOOK_WORKTREE_REMOVE = 'WorktreeRemove'

# Hook event categories for color-coded display
HOOK_EVENT_CATEGORIES = {
    'SessionStart': 'session', 'SessionEnd': 'session',
    'UserPromptSubmit': 'user_input', 'InstructionsLoaded': 'user_input',
    'PreToolUse': 'tool', 'PostToolUse': 'tool', 'PostToolUseFailure': 'tool',
    'PermissionRequest': 'tool', 'PermissionDenied': 'tool',
    'SubagentStart': 'agent', 'SubagentStop': 'agent', 'TeammateIdle': 'agent',
    'TaskCreated': 'task', 'TaskCompleted': 'task',
    'Stop': 'response', 'StopFailure': 'response',
    'FileChanged': 'file', 'CwdChanged': 'file', 'ConfigChange': 'file',
    'PreCompact': 'context', 'PostCompact': 'context',
    'Elicitation': 'mcp', 'ElicitationResult': 'mcp', 'Notification': 'mcp',
    'WorktreeCreate': 'worktree', 'WorktreeRemove': 'worktree',
}

# Excluded tools from display
EXCLUDED_TOOLS = {'Edit'}


# JSONL message types the parser actively processes
KNOWN_MESSAGE_TYPES = {'assistant', 'user', 'progress', 'system', 'result'}

# JSONL message types deliberately ignored (known but not relevant for monitoring)
KNOWN_IGNORED_TYPES = {'file-history-snapshot', 'queue-operation', 'last-prompt', 'custom-title', 'agent-name', 'attachment', 'permission-mode', 'summary'}

# Known API payload top-level keys (Anthropic Messages API)
KNOWN_PAYLOAD_KEYS = {'model', 'messages', 'system', 'tools', 'max_tokens', 'thinking', 'output_config', 'metadata', 'stream', 'context_management', 'temperature', 'top_p', 'top_k', 'tool_choice', 'stop_sequences'}

# Known message content block types
KNOWN_CONTENT_BLOCK_TYPES = {'text', 'thinking', 'tool_use', 'tool_result', 'image'}

# Known tool definition keys
KNOWN_TOOL_DEFINITION_KEYS = {'name', 'description', 'input_schema', 'defer_loading'}

# Known message roles
KNOWN_MESSAGE_ROLES = {'assistant', 'user'}

# Proxy addon — tool stripping (shared between proxy_addon.py and proxy_pane.py)
TOOL_BLOCKLIST = frozenset({
    # Task tools (we use beads)
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
    # Cron tools
    "CronCreate", "CronDelete", "CronList",
    # Worktree tools (workers handle this)
    "EnterWorktree", "ExitWorktree",
    # Unused built-ins
    "LSP", "ListMcpResourcesTool", "ReadMcpResourceTool", "RemoteTrigger",
    "WebFetch", "WebSearch", "web_search",
    # Plan mode (we use iterative-dev skill)
    "EnterPlanMode", "ExitPlanMode",
    # Agent tool (we use MCP tools for git operations)
    "Agent",
    # Other
    "AskUserQuestion", "NotebookEdit",
    # Tool injection (we inject MCP tools directly, replacing ToolSearch entirely)
    "ToolSearch",
    # Unused scheduling + monitoring built-ins
    "ScheduleWakeup", "Monitor",
})

