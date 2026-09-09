"""
Byte-identity harness for src/constants.py's split by constant cluster into src/colors.py (ANSI
colors + backgrounds, PASTEL_* cluster), src/core/modes.py (MODE_* cluster), src/hook_events.py
(HOOK_* cluster + HOOK_EVENT_CATEGORIES), src/pane_error_log.py (PANE_ERROR_LOG_* cluster
absorbed into the module that already owns that concern), and the residual src/constants.py
(timing/size limits + TOOL_BLOCKLIST — zero clusters left).

BEFORE the split: every name below resolves through _NEW_LOCATIONS' default (src.constants,
where they all still live); dumps {name: repr(value)} and hashes it.
AFTER the split: _NEW_LOCATIONS is updated (same commit as the split) to point each moved name at
its new module; the same 70 names resolve from their new homes and hash identically.

Usage (from project root):
    ./venv/bin/python dev/constants/split_byte_identity.py

Prints one HASH line. Run before and after the split; the hash must match.
"""

# INFRASTRUCTURE
import hashlib
import importlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# The exact 70 top-level UPPER_CASE names in src/constants.py at the moment this harness was
# built (pre-split) — frozen here rather than discovered dynamically via vars(), since after the
# split most of them are no longer present in src.constants at all.
_NAMES = [
    'BLUE', 'COLLISION_BG', 'CYAN', 'DIM', 'DIM_GREEN_BG', 'DIM_YELLOW_BG',
    'EXPANDED_MAX_LINES', 'GREEN', 'HOOK_CONFIG_CHANGE', 'HOOK_CWD_CHANGED', 'HOOK_ELICITATION',
    'HOOK_ELICITATION_RESULT', 'HOOK_EVENT_CATEGORIES', 'HOOK_FILE_CHANGED', 'HOOK_NOTIFICATION',
    'HOOK_PERMISSION_DENIED', 'HOOK_PERMISSION_REQUEST', 'HOOK_POST_COMPACT', 'HOOK_POST_TOOL',
    'HOOK_POST_TOOL_FAILURE', 'HOOK_PRE_COMPACT', 'HOOK_PRE_TOOL', 'HOOK_SESSION_END',
    'HOOK_SESSION_START', 'HOOK_STOP', 'HOOK_STOP_FAILURE', 'HOOK_SUBAGENT_START',
    'HOOK_SUBAGENT_STOP', 'HOOK_TASK_COMPLETED', 'HOOK_TASK_CREATED', 'HOOK_TEAMMATE_IDLE',
    'HOOK_USER_PROMPT', 'HOOK_WORKTREE_CREATE', 'HOOK_WORKTREE_REMOVE', 'HOVER_BG',
    'INPUT_POLL_INTERVAL', 'LIGHT_RED_BG', 'MAGENTA', 'MODE_ALL', 'MODE_PROXY', 'MODE_TOKENS',
    'MODE_WARNINGS', 'MODE_WORKERS', 'MODE_WORKER_PROXY', 'ORANGE', 'PANE_ERROR_LOG_KEEP_BYTES',
    'PANE_ERROR_LOG_MAX_BYTES', 'PANE_ERROR_LOG_PATH', 'PASTEL_BLUE', 'PASTEL_GREEN',
    'PASTEL_ORANGE', 'PASTEL_PURPLE', 'POLL_INTERVAL', 'PROXY_MESSAGES_KEEP_LAST',
    'PROXY_REPARSE_INTERVAL_SECONDS', 'PURPLE', 'RED', 'RESET', 'SEARCH_CURRENT_BG',
    'SEARCH_MATCH_BG', 'SOFT_RESET', 'TMUX_HISTORY_LIMIT', 'TOOL_BLOCKLIST',
    'WARNINGS_INITIAL_TAIL_BYTES', 'WARNINGS_POLL_INTERVAL', 'WHITE', 'WORKER_COL_WIDTH',
    'YELLOW', 'ZEBRA_BG_A', 'ZEBRA_BG_B',
]

# Post-split home for every name that moves out of src/constants.py. A name absent here is
# assumed to still live in src.constants — true for the 9 residual timing/size-limit names,
# TOOL_BLOCKLIST, and the entire HOOK_* cluster (+ HOOK_EVENT_CATEGORIES), which stayed per Main's
# explicit direction: a hook-events module would have zero importers (dead code on arrival), and
# HOOK_* is the only cluster left in constants.py once PASTEL_/PANE_/MODE_ leave, which satisfies
# the cluster rule on its own.
_COLOR_NAMES = [
    'BLUE', 'COLLISION_BG', 'CYAN', 'DIM', 'DIM_GREEN_BG', 'DIM_YELLOW_BG', 'GREEN', 'HOVER_BG',
    'LIGHT_RED_BG', 'MAGENTA', 'ORANGE', 'PASTEL_BLUE', 'PASTEL_GREEN', 'PASTEL_ORANGE',
    'PASTEL_PURPLE', 'PURPLE', 'RED', 'RESET', 'SEARCH_CURRENT_BG', 'SEARCH_MATCH_BG',
    'SOFT_RESET', 'WHITE', 'YELLOW', 'ZEBRA_BG_A', 'ZEBRA_BG_B',
]
_MODE_NAMES = [
    'MODE_ALL', 'MODE_PROXY', 'MODE_TOKENS', 'MODE_WARNINGS', 'MODE_WORKERS', 'MODE_WORKER_PROXY',
]
_PANE_ERROR_LOG_NAMES = ['PANE_ERROR_LOG_KEEP_BYTES', 'PANE_ERROR_LOG_MAX_BYTES', 'PANE_ERROR_LOG_PATH']

_NEW_LOCATIONS = {}
_NEW_LOCATIONS.update({n: 'src.colors' for n in _COLOR_NAMES})
_NEW_LOCATIONS.update({n: 'src.core.modes' for n in _MODE_NAMES})
_NEW_LOCATIONS.update({n: 'src.pane_error_log' for n in _PANE_ERROR_LOG_NAMES})

# ORCHESTRATOR


def main():
    dump = _dump_values(_NAMES)
    print(f'HASH: {hashlib.sha256(dump.encode()).hexdigest()}')


# FUNCTIONS

def _resolve(name: str):
    module_path = _NEW_LOCATIONS.get(name, 'src.constants')
    module = importlib.import_module(module_path)
    return getattr(module, name)


# repr(frozenset(...)) / repr(set(...)) order depends on PYTHONHASHSEED's per-process string-hash
# randomization — TOOL_BLOCKLIST would otherwise make this harness's own hash non-reproducible
# across separate runs regardless of any src/constants.py change. Sort (frozen)sets before repr.
def _stable_repr(value) -> str:
    if isinstance(value, (set, frozenset)):
        return repr(sorted(value))
    return repr(value)


def _dump_values(names: list) -> str:
    values = {name: _stable_repr(_resolve(name)) for name in names}
    return json.dumps(values, sort_keys=True)


if __name__ == '__main__':
    main()
