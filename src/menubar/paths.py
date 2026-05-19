# INFRASTRUCTURE
from pathlib import Path

_APP_SUPPORT = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()

SETTINGS_FILE = _APP_SUPPORT / "settings.json"
HOOKS_FILE    = _APP_SUPPORT / "hooks.json"
HOOKS_LOCK    = _APP_SUPPORT / "hooks.lock"
PID_FILE      = _APP_SUPPORT / "menubar.pid"

# FUNCTIONS

# Idempotent migration: move $HOME dotfiles → APP_SUPPORT location on first import
# _old_base defaults to ~; override in tests to point at a tempdir
# NEW wins if both old and new exist — old silently removed (new is the intended state)
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
                old.unlink()       # NEW wins — old silently removed
            else:
                old.rename(new)

_migrate_from_dotfiles()
