# INFRASTRUCTURE
from datetime import datetime
import os
import traceback

# Split out of src/constants.py (PANE_ERROR_LOG_* constant cluster) — this module already owns
# the concern these describe.
PANE_ERROR_LOG_PATH = '/tmp/monitor_cc_error.log'
PANE_ERROR_LOG_MAX_BYTES = 2_000_000   # size that triggers truncation on next write
PANE_ERROR_LOG_KEEP_BYTES = 500_000    # tail bytes kept after truncation

# FUNCTIONS

# Append a timestamped, pane-identified traceback of the currently-handled exception to the
# shared pane-error sink, called from each pane loop's `except Exception:` clause. Caps the sink
# to its last PANE_ERROR_LOG_KEEP_BYTES once it exceeds PANE_ERROR_LOG_MAX_BYTES.
def log_pane_error(pane_name: str) -> None:
    try:
        _cap_log_size()
        with open(PANE_ERROR_LOG_PATH, 'a') as f:
            f.write(f"\n[{datetime.now().isoformat()}] [{pane_name}] error:\n")
            traceback.print_exc(file=f)
    except Exception:  # log-safe: open/seek/write can all fail (disk full, permissions,
        pass            # concurrent truncation from another pane) — must never kill the caller's loop

# Truncate the sink to its tail once it exceeds the size cap — bounds unbounded growth across 8
# pane processes sharing one file, at a fixed read/write cost per truncation (no line/timestamp
# parsing, unlike menubar_log.py's 7-day prune, since this sink can be written to in a tight
# exception-retry loop and a cheap size check must run on every single write)
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
