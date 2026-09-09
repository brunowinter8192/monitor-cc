# INFRASTRUCTURE

# Config values
POLL_INTERVAL = 0.5
INPUT_POLL_INTERVAL = 0.05
WARNINGS_POLL_INTERVAL = 10.0
TMUX_HISTORY_LIMIT = '50000'
EXPANDED_MAX_LINES = 15
PROXY_MESSAGES_KEEP_LAST = 10  # entries at end of list that retain messages for expand UX
PROXY_REPARSE_INTERVAL_SECONDS = 3600  # periodic re-init of proxy panes to release parent pymalloc pages
WORKER_COL_WIDTH = 20  # name-field width; full column = W: + name + space = 23 chars
WARNINGS_INITIAL_TAIL_BYTES = 50_000_000  # max bytes to back-seek on initial log parse to bound pymalloc peak

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
    # Workflow tool (CC 2.1.176+ built-in, ~18.5k-char description, all noise)
    "Workflow",
    # CC 2.1.223+ built-ins (Claude-facing artifact/finding-report/deferred-schema tools, unused)
    "Artifact", "ReportFindings", "DeferredToolPlaceholder",
    # CC 2.1.258+ built-ins (feedback + agent-list, unused)
    "SendFeedback", "ListAgents",
})

