# INFRASTRUCTURE
import os
from pathlib import Path

_PROBE_LOG_PATH = '/tmp/_pane_error_log_probe.log'
_STOP_AFTER_TICKS = 3

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


class _ProbeInjectedError(Exception):
    pass


class _ProbeStop(BaseException):
    pass


# FUNCTIONS

def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


def _read_probe_log():
    log_text = ''
    if os.path.exists(_PROBE_LOG_PATH):
        log_text = Path(_PROBE_LOG_PATH).read_text()
    return log_text
