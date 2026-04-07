# INFRASTRUCTURE

# Colors — 256-color ANSI palette (single source of truth)
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[38;5;35m'
YELLOW = '\033[38;5;220m'
BLUE = '\033[38;5;33m'
CYAN = '\033[38;5;51m'
MAGENTA = '\033[95m'
WHITE = '\033[97m'
PURPLE = '\033[38;5;135m'
ORANGE = '\033[38;5;208m'
PASTEL_BLUE = '\033[38;5;117m'
PASTEL_PURPLE = '\033[38;5;183m'
LIGHT_RED_BG = '\033[48;5;203m'
PASTEL_ORANGE = '\033[38;5;209m'
PASTEL_GREEN = '\033[38;5;114m'
HOVER_BG = '\033[48;5;236m'
DIM = '\033[2m'

# Config values
POLL_INTERVAL = 0.5
INPUT_POLL_INTERVAL = 0.05
LONG_OUTPUT_THRESHOLD = 10000
TMUX_HISTORY_LIMIT = '50000'
EXPANDED_MAX_LINES = 15

# Tool names
TOOL_TASK = 'Task'

# Mode names
MODE_ALL = 'all'
MODE_MAIN = 'main'
MODE_SUBAGENT = 'subagent'
MODE_RULES = 'rules'
MODE_WARNINGS = 'warnings'
MODE_HOOKS = 'hooks'
MODE_TOKENS = 'tokens'
MODE_WORKERS = 'workers'
MODE_SUBAGENTS = 'subagents'
MODE_PROXY = 'proxy'

# Hook events — session lifecycle
HOOK_SESSION_START = 'SessionStart'
HOOK_SESSION_END = 'SessionEnd'

# Hook events — user input
HOOK_USER_PROMPT = 'UserPromptSubmit'
HOOK_INSTRUCTIONS_LOADED = 'InstructionsLoaded'

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
KNOWN_IGNORED_TYPES = {'file-history-snapshot', 'queue-operation', 'last-prompt', 'custom-title', 'agent-name', 'attachment', 'permission-mode'}

# Pane header labels
PANE_HEADERS = {
    'main': 'MAIN',
    'rules': 'RULES',
    'hooks': 'HOOKS',
    'warnings': 'WARNINGS',
    'tokens': 'TOKENS',
    'workers': 'WORKERS',
    'subagents': 'SUBAGENTS',
}
