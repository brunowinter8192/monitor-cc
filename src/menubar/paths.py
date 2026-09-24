# INFRASTRUCTURE
from pathlib import Path

from ..monitor_root import resolve_monitor_cc_root
from .root_report import report_root

_APP_SUPPORT  = Path("~/Library/Application Support/com.brunowinter.monitor-cc-menubar").expanduser()
_SHARED_RULES = Path("~/.claude/shared-rules").expanduser()

SETTINGS_FILE             = _APP_SUPPORT / "settings.json"
HOOKS_FILE                = _APP_SUPPORT / "hooks.json"
PID_FILE                  = _APP_SUPPORT / "menubar.pid"
MONITOR_SWEEP_STATE_FILE  = _APP_SUPPORT / "monitor_sweep_state.json"
MODEL_SELECTION_FILE      = _SHARED_RULES / "model_selection.json"
PROXY_RULES_FILE          = _SHARED_RULES / "proxy_rules.json"

MONITOR_CC_ROOT = resolve_monitor_cc_root(report_root, "PROJECT_ROOT")

_APP_SUPPORT.mkdir(parents=True, exist_ok=True)
