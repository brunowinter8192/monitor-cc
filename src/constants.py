# INFRASTRUCTURE

# Tool names
TOOL_TASK = 'Task'

# Mode names
MODE_ALL = 'all'
MODE_MAIN = 'main'
MODE_SUBAGENT = 'subagent'
MODE_RULES = 'rules'
MODE_WARNINGS = 'warnings'

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
