# INFRASTRUCTURE
import importlib
import os
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ['MONITOR_CC_ROOT'] = str(WORKTREE_ROOT)

from dev.refactoring.strand_runner import check

_FIXED_TERMINAL = os.terminal_size((220, 50))
os.get_terminal_size = lambda fd=1: _FIXED_TERMINAL

_ROOT_PKG = 'src'
mod_wpane = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_wrender = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_render')
mod_gpu = importlib.import_module(f'{_ROOT_PKG}.gpu_pane.pane')
mod_news = importlib.import_module(f'{_ROOT_PKG}.news_pane.pane')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')

PANE_WIDTH = 100


# FUNCTIONS

def _make_error(tool_name='Bash', worker_name='', full_text='error output', input_marker=None):
    return {
        'timestamp': '10:00:00', 'tool_name': tool_name, 'summary': full_text[:80],
        'full_text': full_text, 'worker_name': worker_name,
        'tool_call_input': {'command': input_marker} if input_marker else {},
    }


def _make_preset(name, running=True, healthy=True, port=8000, pid=123):
    return {
        'name': name, 'kind': 'preset', 'running': running, 'healthy': healthy,
        'port': port, 'pid': pid, 'rss_mb': None, 'idle_seconds': None,
        'idle_state_missing': False, 'model_name': None,
    }


def _dispatch_gpu_click(col, row):
    if row == 1:
        return mod_search_bar.handle_search_mouse_press(mod_gpu._gpu_search, col, mod_gpu._GPU_SEARCH_BAR_LABEL)
    for (sc, ec, er), (action, target) in list(mod_gpu._button_regions.items()):
        if row == er and sc <= col <= ec:
            if action == 'refresh':
                return 'refresh'
            if target not in mod_gpu._toggle_state:
                mod_gpu._fire_button(action, target)
                return (action, target)
    return None


def _reset_warnings_state(query: str = ''):
    mod_wpane.tool_errors.clear()
    mod_wpane.error_expand_states.clear()
    mod_wpane.error_line_map.clear()
    mod_wpane.error_hover_row = None
    mod_wpane.error_scroll_offset = 0
    mod_wpane.error_copy_rows.clear()
    mod_wpane._error_copy_feedback_until.clear()
    mod_wpane._error_pane_width = PANE_WIDTH
    mod_wpane._warnings_header_regions.clear()
    mod_wpane._force_refresh = False
    mod_wpane._last_refresh_ts = 1234567890.0
    mod_wpane._warnings_search.query = query
    mod_wpane._warnings_search.focused = False
    mod_wpane._warnings_search.matches = []
    mod_wpane._warnings_search.match_set = set()
    mod_wpane._warnings_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wpane._warnings_search)


def _reset_gpu_state(query: str = ''):
    mod_gpu._button_regions.clear()
    mod_gpu._toggle_state.clear()
    mod_gpu._gpu_search.query = query
    mod_gpu._gpu_search.focused = False
    mod_gpu._gpu_search.matches = []
    mod_gpu._gpu_search.match_set = set()
    mod_gpu._gpu_search.current_idx = 0
    mod_search_bar.clear_selection(mod_gpu._gpu_search)


def _reset_news_state(query: str = ''):
    mod_news._button_regions.clear()
    mod_news._pipeline_proc = None
    mod_news._news_search.query = query
    mod_news._news_search.focused = False
    mod_news._news_search.matches = []
    mod_news._news_search.match_set = set()
    mod_news._news_search.current_idx = 0
    mod_search_bar.clear_selection(mod_news._news_search)


def _capture_clipboard(mod):
    captured = []
    orig = mod.copy_to_clipboard
    mod.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig
