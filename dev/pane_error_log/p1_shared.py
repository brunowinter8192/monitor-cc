# INFRASTRUCTURE
import atexit
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dev.refactoring.strand_runner import check

_PROBE_DIR = tempfile.mkdtemp(prefix='pane_error_log_p1_')
atexit.register(shutil.rmtree, _PROBE_DIR, True)
_PROBE_LOG_PATH = str(Path(_PROBE_DIR) / 'probe.log')
_PROBE_TINY_LOG_PATH = str(Path(_PROBE_DIR) / 'probe_tiny.log')
_PROBE_CAP_LOG_PATH = str(Path(_PROBE_DIR) / 'probe_cap.log')
_STOP_AFTER_TICKS = 3


# FUNCTIONS

class _ProbeInjectedError(Exception):
    pass


class _ProbeStop(BaseException):
    pass


def _read_probe_log():
    log_text = ''
    if Path(_PROBE_LOG_PATH).exists():
        log_text = Path(_PROBE_LOG_PATH).read_text()
    return log_text
