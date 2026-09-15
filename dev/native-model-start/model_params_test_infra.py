# INFRASTRUCTURE
import sys
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy import inject_helpers

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_RESULTS = []


# FUNCTIONS

def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


def _with_config(config, fn):
    with mock.patch.object(inject_helpers, "_load_config", lambda: config):
        return fn()
