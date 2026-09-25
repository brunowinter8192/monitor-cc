# INFRASTRUCTURE
import importlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('MONITOR_CC_ROOT', str(_ROOT))
sys.path.insert(0, str(_ROOT))

from dev.refactoring.strand_runner import strand_workflow
from src.format import format_cache_tracker

_HARNESS = 'dev.panes.render_byte_identity'
_STRANDS = [
    'strand_tiny_heights_do_not_raise',
    'strand_tiny_height_keeps_one_line',
    'strand_normal_heights_unchanged',
]
_TINY_HEIGHTS = (-1, 0, 1)
_NORMAL_HEIGHTS = (2, 3, 5, 10, 50)
_WIDTHS = (10, 40, 100)

# ORCHESTRATOR

def test_tiny_pane_viewport_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_tiny_pane_viewport')

# FUNCTIONS

def strand_tiny_heights_do_not_raise() -> None:
    for height in _TINY_HEIGHTS:
        for width in _WIDTHS:
            _render(height, width)
            print(f'  PASS  height={height} width={width} renders')

def strand_tiny_height_keeps_one_line() -> None:
    for height in _TINY_HEIGHTS:
        lines, keys, _sticky, _start, _count = _render(height, 40)
        _require(len(lines) == 1 and len(keys) == 1, f'height={height} lines={len(lines)}')
        print(f'  PASS  height={height} shows exactly one line')

def strand_normal_heights_unchanged() -> None:
    for height in _NORMAL_HEIGHTS:
        lines, keys, _sticky, _start, _count = _render(height, 40)
        _require(len(lines) == len(keys) and 0 < len(lines) <= height - 1, f'height={height} lines={len(lines)}')
        print(f'  PASS  height={height} shows at most {height - 1} lines')

def _render(height: int, width: int) -> tuple:
    harness = importlib.import_module(_HARNESS)
    turns, response_rid_map = harness._make_rate_limit_turns()
    return format_cache_tracker(turns, {(0, 0): True}, height, width, 0, response_rid_map,
                                turn_cache=harness._token_turn_cache())

def _require(condition: bool, detail: str) -> None:
    if not condition:
        print(f'  FAIL  {detail}')
        raise AssertionError(detail)

if __name__ == '__main__':
    sys.exit(test_tiny_pane_viewport_workflow())
