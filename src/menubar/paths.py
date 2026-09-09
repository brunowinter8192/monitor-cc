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

# FUNCTIONS

def _migrate_from_dotfiles(_old_base: Path = Path.home()) -> None:
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    _OLD = {
        _old_base / ".monitor_cc_menubar_settings.json": SETTINGS_FILE,
        _old_base / ".monitor_cc_menubar_hooks.json":    HOOKS_FILE,
        _old_base / ".monitor_cc_menubar_hooks.lock":    HOOKS_LOCK,
        _old_base / ".monitor_cc_menubar.pid":           PID_FILE,
    }
    for old, new in _OLD.items():
        if old.exists():
            if new.exists():
                old.unlink()
            else:
                old.rename(new)

_migrate_from_dotfiles()

def _migrate_from_old_bundle_id() -> None:
    _old = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()
    if not _old.exists():
        return
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    for fname in ("settings.json", "hooks.json", "hooks.lock",
                  "ghostty_cwd_uuid.json", "orchestrator_signals.json",
                  "menubar.pid", "menubar.log", "cwd_desktop.json"):
        old_f = _old / fname
        new_f = _APP_SUPPORT / fname
        if old_f.exists() and not new_f.exists():
            old_f.rename(new_f)

_migrate_from_old_bundle_id()
