# INFRASTRUCTURE
import hashlib
import importlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_NAMES = [
    'BLUE', 'COLLISION_BG', 'CYAN', 'DIM', 'DIM_GREEN_BG', 'DIM_YELLOW_BG',
    'EXPANDED_MAX_LINES', 'GREEN', 'HOVER_BG',
    'INPUT_POLL_INTERVAL', 'LIGHT_RED_BG', 'MAGENTA', 'MODE_ALL', 'MODE_PROXY', 'MODE_TOKENS',
    'MODE_WARNINGS', 'MODE_WORKER_TOKENS', 'MODE_WORKER_PROXY', 'ORANGE', 'PANE_ERROR_LOG_KEEP_BYTES',
    'PANE_ERROR_LOG_MAX_BYTES', 'PANE_ERROR_LOG_PATH', 'PASTEL_BLUE', 'PASTEL_GREEN',
    'PASTEL_ORANGE', 'PASTEL_PURPLE', 'POLL_INTERVAL', 'PROXY_MESSAGES_KEEP_LAST',
    'PROXY_REPARSE_INTERVAL_SECONDS', 'PURPLE', 'RED', 'RESET', 'SEARCH_CURRENT_BG',
    'SEARCH_MATCH_BG', 'SOFT_RESET', 'TMUX_HISTORY_LIMIT', 'TOOL_BLOCKLIST',
    'WARNINGS_INITIAL_TAIL_BYTES', 'WARNINGS_POLL_INTERVAL', 'WHITE', 'WORKER_COL_WIDTH',
    'YELLOW', 'ZEBRA_BG_A', 'ZEBRA_BG_B',
]

_COLOR_NAMES = [
    'BLUE', 'COLLISION_BG', 'CYAN', 'DIM', 'DIM_GREEN_BG', 'DIM_YELLOW_BG', 'GREEN', 'HOVER_BG',
    'LIGHT_RED_BG', 'MAGENTA', 'ORANGE', 'PASTEL_BLUE', 'PASTEL_GREEN', 'PASTEL_ORANGE',
    'PASTEL_PURPLE', 'PURPLE', 'RED', 'RESET', 'SEARCH_CURRENT_BG', 'SEARCH_MATCH_BG',
    'SOFT_RESET', 'WHITE', 'YELLOW', 'ZEBRA_BG_A', 'ZEBRA_BG_B',
]
_MODE_NAMES = [
    'MODE_ALL', 'MODE_PROXY', 'MODE_TOKENS', 'MODE_WARNINGS', 'MODE_WORKER_TOKENS', 'MODE_WORKER_PROXY',
]
_PANE_ERROR_LOG_NAMES = ['PANE_ERROR_LOG_KEEP_BYTES', 'PANE_ERROR_LOG_MAX_BYTES', 'PANE_ERROR_LOG_PATH']

_NEW_LOCATIONS = {}
_NEW_LOCATIONS.update({n: 'src.colors' for n in _COLOR_NAMES})
_NEW_LOCATIONS.update({n: 'src.core.modes' for n in _MODE_NAMES})
_NEW_LOCATIONS.update({n: 'src.pane_error_log' for n in _PANE_ERROR_LOG_NAMES})


# ORCHESTRATOR

def main():
    dump = _dump_values(_NAMES)
    print_hash(dump)


# FUNCTIONS

def _dump_values(names: list) -> str:
    values = {name: _stable_repr(_resolve(name)) for name in names}
    return json.dumps(values, sort_keys=True)


def _stable_repr(value) -> str:
    if isinstance(value, (set, frozenset)):
        return repr(sorted(value))
    return repr(value)


def _resolve(name: str):
    module_path = _NEW_LOCATIONS.get(name, 'src.constants')
    module = importlib.import_module(module_path)
    return getattr(module, name)


def print_hash(dump):
    print(f'HASH: {hashlib.sha256(dump.encode()).hexdigest()}')


if __name__ == '__main__':
    main()
