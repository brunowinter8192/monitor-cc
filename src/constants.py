# INFRASTRUCTURE

POLL_INTERVAL = 0.5
INPUT_POLL_INTERVAL = 0.05
WARNINGS_POLL_INTERVAL = 10.0
TMUX_HISTORY_LIMIT = '50000'
EXPANDED_MAX_LINES = 15
PROXY_MESSAGES_KEEP_LAST = 10
PROXY_REPARSE_INTERVAL_SECONDS = 3600
WORKER_COL_WIDTH = 20
WARNINGS_INITIAL_TAIL_BYTES = 50_000_000

HOOK_SESSION_START = 'SessionStart'
HOOK_SESSION_END = 'SessionEnd'

HOOK_USER_PROMPT = 'UserPromptSubmit'

HOOK_PRE_TOOL = 'PreToolUse'
HOOK_POST_TOOL = 'PostToolUse'
HOOK_POST_TOOL_FAILURE = 'PostToolUseFailure'
HOOK_PERMISSION_REQUEST = 'PermissionRequest'
HOOK_PERMISSION_DENIED = 'PermissionDenied'

HOOK_SUBAGENT_START = 'SubagentStart'
HOOK_SUBAGENT_STOP = 'SubagentStop'
HOOK_TEAMMATE_IDLE = 'TeammateIdle'

HOOK_TASK_CREATED = 'TaskCreated'
HOOK_TASK_COMPLETED = 'TaskCompleted'

HOOK_STOP = 'Stop'
HOOK_STOP_FAILURE = 'StopFailure'

HOOK_FILE_CHANGED = 'FileChanged'
HOOK_CWD_CHANGED = 'CwdChanged'
HOOK_CONFIG_CHANGE = 'ConfigChange'

HOOK_PRE_COMPACT = 'PreCompact'
HOOK_POST_COMPACT = 'PostCompact'

HOOK_ELICITATION = 'Elicitation'
HOOK_ELICITATION_RESULT = 'ElicitationResult'
HOOK_NOTIFICATION = 'Notification'

HOOK_WORKTREE_CREATE = 'WorktreeCreate'
HOOK_WORKTREE_REMOVE = 'WorktreeRemove'

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

TOOL_BLOCKLIST = frozenset({
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
    "CronCreate", "CronDelete", "CronList",
    "EnterWorktree", "ExitWorktree",
    "LSP", "ListMcpResourcesTool", "ReadMcpResourceTool", "RemoteTrigger",
    "WebFetch", "WebSearch", "web_search",
    "EnterPlanMode", "ExitPlanMode",
    "Agent",
    "AskUserQuestion", "NotebookEdit",
    "ToolSearch",
    "ScheduleWakeup", "Monitor",
    "Workflow",
    "Artifact", "ReportFindings", "DeferredToolPlaceholder",
    "SendFeedback", "ListAgents",
})

