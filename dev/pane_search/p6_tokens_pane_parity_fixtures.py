# INFRASTRUCTURE
import importlib
import os
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_tp = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
mod_ts = importlib.import_module(f'{_ROOT_PKG}.panes.token_search')
mod_tf = importlib.import_module(f'{_ROOT_PKG}.format.token_format')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')
mod_monitor = importlib.import_module(f'{_ROOT_PKG}.core.monitor')
mod_parser = importlib.import_module(f'{_ROOT_PKG}.proxy_display.parser')
mod_side_logs = importlib.import_module(f'{_ROOT_PKG}.proxy_display.side_logs')

PANE_WIDTH = 100
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

# Synthetic turn — one call, optionally carrying a marker in its own prompt (turn-level match
# surface) and/or a content_blocks text preview (call-level match surface, only found by the
# matcher's force-expand, invisible when collapsed in a real render).
def _make_turn(idx: int, prompt_marker: str = None, call_marker: str = None,
                cache_read: int = 1000, cache_creation: int = 0) -> dict:
    prompt = f"turn {idx}" + (f" {prompt_marker}" if prompt_marker else "")
    content_blocks = [{'type': 'text', 'preview': call_marker, 'chars': len(call_marker)}] if call_marker else []
    call = {
        'cache_read': cache_read, 'cache_creation': cache_creation, 'direct': 0, 'output_tokens': 50,
        'content_blocks': content_blocks,
    }
    return {'prompt': prompt, 'timestamp': f'2026-01-01T00:{idx:02d}:00Z', 'api_calls': [call]}


def _reset_state(query: str = ''):
    mod_tp.cache_expand_states.clear()
    mod_tp.cache_line_map.clear()
    mod_tp.cache_hover_row = None
    mod_tp.cache_scroll_offset = 0
    mod_tp.cache_copy_rows.clear()
    mod_tp._cache_copy_feedback_until.clear()
    mod_tp._cache_pane_width = PANE_WIDTH
    mod_tp._cache_turns.clear()
    mod_tp._cache_current_filepath = None
    mod_tp._tokens_nav.clear()
    mod_tp._tokens_search.query = query
    mod_tp._tokens_search.focused = False
    mod_tp._tokens_search.matches = []
    mod_tp._tokens_search.match_set = set()
    mod_tp._tokens_search.current_idx = 0
    mod_search_bar.clear_selection(mod_tp._tokens_search)


def _capture_clipboard():
    captured = []
    orig = mod_tp.copy_to_clipboard
    mod_tp.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig
