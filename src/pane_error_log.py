# INFRASTRUCTURE
from datetime import datetime
import os
import traceback

PANE_ERROR_LOG_PATH = '/tmp/monitor_cc_error.log'
PANE_ERROR_LOG_MAX_BYTES = 2_000_000
PANE_ERROR_LOG_KEEP_BYTES = 500_000

# FUNCTIONS

def log_pane_error(pane_name: str) -> None:
    try:
        _cap_log_size()
        with open(PANE_ERROR_LOG_PATH, 'a') as f:
            f.write(f"\n[{datetime.now().isoformat()}] [{pane_name}] error:\n")
            traceback.print_exc(file=f)
    except Exception:
        pass

def _cap_log_size() -> None:
    if not os.path.exists(PANE_ERROR_LOG_PATH):
        return
    if os.path.getsize(PANE_ERROR_LOG_PATH) <= PANE_ERROR_LOG_MAX_BYTES:
        return
    with open(PANE_ERROR_LOG_PATH, 'rb') as f:
        f.seek(-PANE_ERROR_LOG_KEEP_BYTES, os.SEEK_END)
        tail = f.read()
    with open(PANE_ERROR_LOG_PATH, 'wb') as f:
        f.write(tail)
