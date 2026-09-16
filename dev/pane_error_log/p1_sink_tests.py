# INFRASTRUCTURE
import os
from pathlib import Path

from p1_shared import check
from p1_pane_modules import pel


# FUNCTIONS

# Test: a failing log write itself must not kill the calling loop (deliverable 4) — exercises
# both failure points inside src/pane_error_log.py: the open()/write() in log_pane_error, and the
# seek()/truncate in _cap_log_size (forced via an artificially tiny MAX_BYTES on a tiny real file)
def test_failing_log_write_does_not_raise():
    print("\n[Test] a failing log write cannot raise out of log_pane_error (deliverable 4)")

    orig_path = pel.PANE_ERROR_LOG_PATH
    pel.PANE_ERROR_LOG_PATH = '/nonexistent_dir_xyz_probe/monitor_cc_error.log'
    try:
        raised = False
        try:
            pel.log_pane_error('probe')
        except Exception:
            raised = True
    finally:
        pel.PANE_ERROR_LOG_PATH = orig_path
    check("open() failure (nonexistent parent dir) does not raise out of log_pane_error", not raised)

    orig_path, orig_max, orig_keep = pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES
    tiny_log = '/tmp/_pane_error_log_probe_tiny.log'
    Path(tiny_log).write_text('short')  # 5 bytes
    pel.PANE_ERROR_LOG_PATH = tiny_log
    pel.PANE_ERROR_LOG_MAX_BYTES = 0             # force the truncation branch on every call
    pel.PANE_ERROR_LOG_KEEP_BYTES = 500_000      # seek(-500000, SEEK_END) on a 5-byte file -> OSError
    try:
        raised = False
        try:
            pel.log_pane_error('probe')
        except Exception:
            raised = True
    finally:
        pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES = orig_path, orig_max, orig_keep
        os.remove(tiny_log)
    check("_cap_log_size seek-underflow (OSError) does not raise out of log_pane_error", not raised)


# Test: the sink is size-capped, not left to grow unbounded
def test_log_size_capping():
    print("\n[Test] sink truncates to its tail once it exceeds the size cap")
    orig_path, orig_max, orig_keep = pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES
    cap_log = '/tmp/_pane_error_log_probe_cap.log'
    Path(cap_log).write_text('X' * 1000 + 'TAIL_MARKER')
    pel.PANE_ERROR_LOG_PATH = cap_log
    pel.PANE_ERROR_LOG_MAX_BYTES = 500
    pel.PANE_ERROR_LOG_KEEP_BYTES = 20
    try:
        pel._cap_log_size()
        text = Path(cap_log).read_text()
    finally:
        pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES = orig_path, orig_max, orig_keep
        os.remove(cap_log)
    check("oversized sink truncated below the pre-cap size", len(text) < 1011)
    check("truncated sink kept the TAIL (most recent bytes), not the head", text.endswith('TAIL_MARKER'))
