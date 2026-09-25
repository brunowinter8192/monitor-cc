# INFRASTRUCTURE
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.menubar.paths import _APP_SUPPORT

MENUBAR_LOG    = _APP_SUPPORT / 'menubar.log'
RETENTION_SECS = 7 * 86400

_last_by_key: Dict[str, Optional[str]] = {}

# FUNCTIONS

def log_menubar(category: str, message: str) -> None:
    try:
        MENUBAR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(MENUBAR_LOG, 'a') as fh:
            fh.write(f'{datetime.now().isoformat(timespec="seconds")} [{category}] {message}\n')
    except Exception as exc:
        print(f'[menubar_log] write failed category={category}: {exc!r}', file=sys.stderr)

def log_menubar_change(category: str, key: str, message: Optional[str]) -> None:
    if _last_by_key.get(key) == message:
        return
    _last_by_key[key] = message
    if message is not None:
        log_menubar(category, message)

def cleanup_old_lines() -> None:
    try:
        if not MENUBAR_LOG.exists():
            return
        cutoff = datetime.now() - timedelta(seconds=RETENTION_SECS)
        lines = MENUBAR_LOG.read_text().splitlines(keepends=True)
        kept = []
        for line in lines:
            if not _is_expired(line, cutoff):
                kept.append(line)
        MENUBAR_LOG.write_text(''.join(kept))
    except Exception as exc:
        print(f'[menubar_log] cleanup failed: {exc!r}', file=sys.stderr)

def _is_expired(line: str, cutoff: datetime) -> bool:
    try:
        return datetime.fromisoformat(line[:19]) < cutoff
    except ValueError:
        return False
