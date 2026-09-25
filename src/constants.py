# INFRASTRUCTURE

import re

POLL_INTERVAL = 0.5
INPUT_POLL_INTERVAL = 0.05
WARNINGS_POLL_INTERVAL = 10.0
TMUX_HISTORY_LIMIT = '50000'
EXPANDED_MAX_LINES = 15
PROXY_MESSAGES_KEEP_LAST = 10
PROXY_REPARSE_INTERVAL_SECONDS = 3600
WORKER_COL_WIDTH = 20
NO_TIME_PLACEHOLDER = '--:--:--'
WARNINGS_INITIAL_TAIL_BYTES = 50_000_000
COPY_FLASH_SYMBOL = 'v'

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

BASH_MOD_EDIT = "edit"
BASH_MOD_FROM_SCRATCH = "from_scratch"
BASH_MOD_UNDETERMINED = "undetermined"

BASH_FILE_MODIFICATION_FORMS = (
    {"label": "sed -i", "pattern": re.compile(r'\bsed\s+.{0,60}?-i\b'), "determinacy": BASH_MOD_EDIT},
    {"label": "perl -pi/-ni", "pattern": re.compile(r'\bperl\s+.{0,20}?-\S*i\S*'), "determinacy": BASH_MOD_EDIT},
    {"label": "gawk -i inplace", "pattern": re.compile(r'\bg?awk\s+-i\s*inplace\b'), "determinacy": BASH_MOD_EDIT},
    {"label": "python open() mode r+", "pattern": re.compile(r"\bopen\([^)]*['\"]r\+b?['\"]"), "determinacy": BASH_MOD_EDIT},
    {"label": "python open() mode x", "pattern": re.compile(r"\bopen\([^)]*['\"]x\+?b?['\"]"), "determinacy": BASH_MOD_FROM_SCRATCH},
    {"label": "truncating redirect >", "pattern": re.compile(r'(?<!>)>(?!>|\||&)\s*(?!/dev/(?:null|stdout|stderr)\b)'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "force-clobber redirect >|", "pattern": re.compile(r'>\|'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "appending redirect >>", "pattern": re.compile(r'>>(?!>)\s*(?!/dev/(?:null|stdout|stderr)\b)'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "read-write redirect <>", "pattern": re.compile(r'<>'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "tee -a", "pattern": re.compile(r'\btee\s+(?:\S+\s+)*(-\S*a\S*\b|--append\b)'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "tee (truncating)", "pattern": re.compile(r'\btee\b'), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "python open() mode w", "pattern": re.compile(r"\bopen\([^)]*['\"]w\+?b?['\"]"), "determinacy": BASH_MOD_UNDETERMINED},
    {"label": "python open() mode a", "pattern": re.compile(r"\bopen\([^)]*['\"]a\+?b?['\"]"), "determinacy": BASH_MOD_UNDETERMINED},
)
