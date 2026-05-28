# INFRASTRUCTURE
from datetime import datetime, timedelta

# From paths.py: APP_SUPPORT dir (~/.../com.brunowinter.monitor_cc_menubar/)
from .paths import _APP_SUPPORT

MENUBAR_LOG    = _APP_SUPPORT / 'menubar.log'
RETENTION_SECS = 7 * 86400

# FUNCTIONS

# Append one timestamped line to MENUBAR_LOG; exception-safe (Carbon/AppKit callbacks must never raise)
def log_menubar(category: str, message: str) -> None:
    try:
        MENUBAR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(MENUBAR_LOG, 'a') as fh:
            fh.write(f'{datetime.now().isoformat(timespec="seconds")} [{category}] {message}\n')
    except Exception:  # log-safe: must never raise into Carbon/AppKit callbacks
        pass

# Drop lines older than 7 days from MENUBAR_LOG and rewrite; exception-safe
# Lines without a parseable ISO timestamp at line[:19] are kept (safe default)
def cleanup_old_lines() -> None:
    try:
        if not MENUBAR_LOG.exists():
            return
        cutoff = datetime.now() - timedelta(seconds=RETENTION_SECS)
        lines = MENUBAR_LOG.read_text().splitlines(keepends=True)
        kept = []
        for line in lines:
            try:
                if datetime.fromisoformat(line[:19]) < cutoff:
                    continue
            except Exception:  # unparseable timestamp → keep line (safe default)
                pass
            kept.append(line)
        MENUBAR_LOG.write_text(''.join(kept))
    except Exception:  # log-safe: must never raise into AppKit tick
        pass
