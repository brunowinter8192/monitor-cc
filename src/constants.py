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
PASTEL_ORANGE = '\033[38;5;216m'

# Config values
POLL_INTERVAL = 0.5
LONG_OUTPUT_THRESHOLD = 10000
TMUX_HISTORY_LIMIT = '50000'

# Tool names
TOOL_TASK = 'Task'

# Mode names
MODE_ALL = 'all'
MODE_MAIN = 'main'
MODE_SUBAGENT = 'subagent'
MODE_RULES = 'rules'
MODE_WARNINGS = 'warnings'
MODE_HOOKS = 'hooks'

# Hook events
HOOK_USER_PROMPT = 'UserPromptSubmit'
HOOK_PRE_TOOL = 'PreToolUse'
HOOK_INSTRUCTIONS_LOADED = 'InstructionsLoaded'

# Excluded tools from display
EXCLUDED_TOOLS = {'Edit'}

# Regex pattern for system-reminder tags
SYSTEM_REMINDER_PATTERN = r'<system-reminder>.*?</system-reminder>'

# JSONL message types the parser actively processes
KNOWN_MESSAGE_TYPES = {'assistant', 'user', 'progress', 'system', 'result'}

# JSONL message types deliberately ignored (known but not relevant for monitoring)
KNOWN_IGNORED_TYPES = {'file-history-snapshot', 'queue-operation', 'last-prompt', 'custom-title', 'agent-name'}

# Pane header labels
PANE_HEADERS = {
    'main': 'MAIN',
    'rules': 'RULES',
    'subagent': 'SUBAGENTS',
    'hooks': 'HOOKS',
    'warnings': 'WARNINGS',
}
