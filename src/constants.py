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

