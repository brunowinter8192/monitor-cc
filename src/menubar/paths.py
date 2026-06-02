# INFRASTRUCTURE
from pathlib import Path

_APP_SUPPORT = Path("~/Library/Application Support/com.brunowinter.monitor-cc-menubar").expanduser()

SETTINGS_FILE             = _APP_SUPPORT / "settings.json"
HOOKS_FILE                = _APP_SUPPORT / "hooks.json"
HOOKS_LOCK                = _APP_SUPPORT / "hooks.lock"
PID_FILE                  = _APP_SUPPORT / "menubar.pid"
QUEUE_FILE                = _APP_SUPPORT / "msg_queue.json"
QUEUE_LOCK                = _APP_SUPPORT / "queue.lock"
GHOSTTY_CWD_UUID_FILE     = _APP_SUPPORT / "ghostty_cwd_uuid.json"
ORCHESTRATOR_SIGNALS_FILE = _APP_SUPPORT / "orchestrator_signals.json"  # {tmux_session_name: send_unix_ts}; written by worker-cli send

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

# Idempotent migration: move old bundle-id dir → new bundle-id dir on first import
# OLD: ~/Library/Application Support/com.brunowinter.monitor_cc_menubar/
# NEW: ~/Library/Application Support/com.brunowinter.monitor-cc-menubar/ (= _APP_SUPPORT)
# NEW wins: files already present at new location are skipped (no clobber)
def _migrate_from_old_bundle_id() -> None:
    _old = Path("~/Library/Application Support/com.brunowinter.monitor_cc_menubar").expanduser()
    if not _old.exists():
        return
    _APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    for fname in ("settings.json", "hooks.json", "hooks.lock", "msg_queue.json",
                  "queue.lock", "ghostty_cwd_uuid.json", "orchestrator_signals.json",
                  "menubar.pid", "menubar.log", "cwd_desktop.json"):
        old_f = _old / fname
        new_f = _APP_SUPPORT / fname
        if old_f.exists() and not new_f.exists():
            old_f.rename(new_f)

_migrate_from_old_bundle_id()
