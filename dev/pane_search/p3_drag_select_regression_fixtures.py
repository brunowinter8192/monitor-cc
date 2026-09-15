# INFRASTRUCTURE
import importlib
import os
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_pane = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')

PANE_WIDTH = 80
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

def _reset_state(query: str = ''):
    mod_pane.proxy_entries.clear()
    mod_pane.proxy_expand_states.clear()
    mod_pane.proxy_line_map.clear()
    mod_pane._proxy_search.query = query
    mod_pane._proxy_search.focused = False
    mod_pane._proxy_search.dragging = False
    mod_pane._proxy_search.sel_anchor = None
    mod_pane._proxy_search.sel_end = None
    mod_pane._proxy_pane_width = PANE_WIDTH
    mod_pane._proxy_undo_stack.clear()
    mod_pane._proxy_just_expanded = None


def _capture_clipboard():
    captured = []
    orig = mod_pane.copy_to_clipboard
    mod_pane.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig
