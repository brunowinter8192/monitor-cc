# INFRASTRUCTURE
import os
from pathlib import Path

_APP_SUPPORT  = Path("~/Library/Application Support/com.brunowinter.monitor-cc-menubar").expanduser()
_SHARED_RULES = Path("~/.claude/shared-rules").expanduser()

SETTINGS_FILE             = _APP_SUPPORT / "settings.json"
HOOKS_FILE                = _APP_SUPPORT / "hooks.json"
HOOKS_LOCK                = _APP_SUPPORT / "hooks.lock"
PID_FILE                  = _APP_SUPPORT / "menubar.pid"
GHOSTTY_CWD_UUID_FILE     = _APP_SUPPORT / "ghostty_cwd_uuid.json"
ORCHESTRATOR_SIGNALS_FILE = _APP_SUPPORT / "orchestrator_signals.json"
MONITOR_SWEEP_STATE_FILE  = _APP_SUPPORT / "monitor_sweep_state.json"
MODEL_SELECTION_FILE      = _SHARED_RULES / "model_selection.json"
PROXY_RULES_FILE          = _SHARED_RULES / "proxy_rules.json"

MONITOR_CC_ROOT = (Path(os.environ["PROJECT_ROOT"]) if os.environ.get("PROJECT_ROOT")
                   else Path(__file__).resolve().parents[2])

_APP_SUPPORT.mkdir(parents=True, exist_ok=True)
