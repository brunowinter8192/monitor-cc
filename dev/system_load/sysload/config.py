# INFRASTRUCTURE
import os
from pathlib import Path

SNAPSHOT_DIR = Path('/tmp/sysload')
TOP_SAMPLE_SECONDS = 1
TOP_SAMPLES = 2
SUBPROCESS_TIMEOUT_SECONDS = 15

MONITOR_SESSION_PREFIX = 'monitor_cc_'
WORKER_SESSION_PREFIX = 'worker-'
WORKER_PROXY_MARKER = '.proxy_addon_live_worker_'
MAIN_PROXY_MARKER = '.proxy_addon_live_'
TASKS_BASE = Path(f'/tmp/claude-{os.getuid()}')
TASK_OUTPUT_SUFFIX = '.output'
ANCESTRY_MAX_HOPS = 8

MINERU_ROOTS = (str(Path.home() / 'Documents' / 'ai' / 'Mineru'),)
MINERU_ENTRY_SCRIPT = 'workflow.py'
MINERU_ENTRY_ARGUMENT = 'convert'
MINERU_BIN_SUFFIXES = ('/venv/bin/mineru', '/venv3/bin/mineru')
MINERU_MODULE_TOKEN = 'mineru.cli.fast_api'

KILLABLE_APP_PREFIXES = {
    'Firefox': '/Applications/Firefox.app/Contents/MacOS/',
}
DOUBTFUL_ALWAYS_NAMES = ('llama-server',)
DOUBTFUL_ALWAYS_PATH_PARTS = ('/Applications/OrbStack.app/',)

SYSTEM_PATH_PREFIXES = (
    '/System/', '/usr/libexec/', '/usr/sbin/', '/sbin/', '/Library/Apple/',
)
USER_APP_PATH_PREFIXES = ('/System/Applications/',)
ESSENTIAL_NAMES = (
    'launchd', 'kernel_task', 'WindowServer', 'Finder', 'Dock',
    'loginwindow', 'SystemUIServer',
)
ESSENTIAL_PATH_PARTS = (
    '/Applications/Ghostty.app/',
    '/monitor-cc-menubar.app/Contents/MacOS/',
)
TMUX_NAME = 'tmux'

DOUBTFUL_CPU_NOW_PERCENT = 5.0
DOUBTFUL_RSS_MB = 500.0
DOUBTFUL_BURN_RATIO = 0.05
DOUBTFUL_BURN_MIN_CPU_SECONDS = 600.0
BGSHELL_STALE_AGE_SECONDS = 900

REPORT_HOT_CPU_NOW_PERCENT = 2.0
REPORT_HOT_RSS_MB = 300.0
COMMAND_MAX_CHARS = 220
CHAIN_MAX_ENTRIES = 6

GROUP_KILLABLE = 'killable'
GROUP_DOUBTFUL = 'doubtful'
GROUP_ESSENTIAL = 'essential'
GROUPS = (GROUP_KILLABLE, GROUP_DOUBTFUL, GROUP_ESSENTIAL)

ACTION_TMUX_SESSION = 'tmux_kill_session'
ACTION_PID = 'kill_pid'
