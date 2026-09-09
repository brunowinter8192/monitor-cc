# INFRASTRUCTURE
from typing import List, Optional, Set

from .colors import RESET, WHITE, CYAN
from .utils import _cell_width, truncate_visible

_SRCH_LABEL = '\033[38;2;108;112;134m'
_SRCH_IDLE  = '\033[38;2;166;173;200m'

KILL_LINE_CHAR = '\x15'

_BG_RESTORE_SENTINEL = '\033[999m'

# FUNCTIONS

class SearchState:
    def __init__(self):
        self.query: str = ''
        self.focused: bool = False
        self.matches: List = []
        self.match_set: Set = set()
        self.current_idx: int = 0
        self.dragging: bool = False
        self.sel_anchor: Optional[int] = None
        self.sel_end: Optional[int] = None

def clear_selection(state: SearchState) -> None:
    state.dragging = False
    state.sel_anchor = None
    state.sel_end = None

def handle_search_cancel(state: SearchState) -> bool:
    state.focused = False
    state.query = ''
    state.matches = []
    state.match_set = set()
    clear_selection(state)
    return True

def handle_search_input(state: SearchState, char: str, on_commit, kill_line_char: str = KILL_LINE_CHAR, max_len: int = 200) -> bool:
    had_selection = state.sel_anchor is not None
    sel_range = None
    if state.sel_anchor is not None and state.sel_end is not None:
        s, e = sorted((state.sel_anchor, state.sel_end))
        if s != e:
            sel_range = (s, e)
    clear_selection(state)
    if char == kill_line_char:
        state.query = ''
        return True
    if char in ('\x7f', '\x08'):
        if sel_range is not None:
            s, e = sel_range
            state.query = state.query[:s] + state.query[e:]
        else:
            state.query = state.query[:-1]
        return True
    if char in ('\r', '\n'):
        on_commit(state)
        state.focused = False
        return True
    if char.isprintable():
        if len(state.query) < max_len:
            state.query += char
            return True
    return had_selection

def col_to_query_index(col: int, query: str, label: str) -> int:
    rel = col - 1 - len(label)
    if rel <= 0:
        return 0
    pos = 0
    for idx, ch in enumerate(query):
        w = _cell_width(ch)
        if rel < pos + w:
            return idx if (rel - pos) * 2 < w else idx + 1
        pos += w
    return len(query)

def handle_search_mouse_press(state: SearchState, col: int, label: str) -> bool:
    state.focused = True
    idx = col_to_query_index(col, state.query, label)
    state.sel_anchor = idx
    state.sel_end = idx
    state.dragging = True
    return True

def handle_search_mouse_motion(state: SearchState, col: int, label: str) -> bool:
    state.sel_end = col_to_query_index(col, state.query, label)
    return True

def handle_search_mouse_release(state: SearchState, copy_to_clipboard_fn) -> bool:
    if not state.dragging:
        return False
    state.dragging = False
    if state.sel_anchor is None or state.sel_end is None:
        return False
    start, end = sorted((state.sel_anchor, state.sel_end))
    if start == end:
        clear_selection(state)
        return True
    copy_to_clipboard_fn(state.query[start:end])
    return True

def render_search_bar(state: SearchState, pane_width: int, label: str = 'search: ', show_counter: bool = True) -> str:
    cursor = '_' if state.focused else ''
    left_plain = f"{label}{state.query}{cursor}"
    left_vis = sum(_cell_width(ch) for ch in left_plain)
    m = len(state.matches)
    if show_counter and state.query and m > 0:
        counter_plain = f"{state.current_idx + 1}/{m}"
        cnt_color = CYAN
    elif show_counter and state.query:
        counter_plain = "0/0"
        cnt_color = _SRCH_LABEL
    else:
        counter_plain = ""
        cnt_color = _SRCH_LABEL
    right_vis = sum(_cell_width(ch) for ch in counter_plain) + (1 if counter_plain else 0)
    gap = max(0, pane_width - left_vis - right_vis)
    query_color = WHITE if state.focused else _SRCH_IDLE
    cursor_part = f"{CYAN}_" if state.focused else ""
    counter_part = f" {cnt_color}{counter_plain}{RESET}" if counter_plain else ""
    if state.sel_anchor is not None and state.sel_end is not None:
        sel_start, sel_end = sorted((state.sel_anchor, state.sel_end))
    else:
        sel_start = sel_end = 0
    if sel_start != sel_end:
        before = state.query[:sel_start]
        selected = state.query[sel_start:sel_end]
        after = state.query[sel_end:]
        query_part = f"{query_color}{before}{RESET}\033[7m{selected}\033[27m{query_color}{after}{RESET}"
    else:
        query_part = f"{query_color}{state.query}{RESET}"
    bar = (
        f"{_SRCH_LABEL}{label}{RESET}"
        f"{query_part}"
        f"{cursor_part}{RESET}"
        f"{' ' * gap}"
        f"{counter_part}"
    )
    return truncate_visible(bar, pane_width)

def resolve_bg_restore(line: str, chosen_bg: str) -> str:
    if _BG_RESTORE_SENTINEL in line:
        return line.replace(_BG_RESTORE_SENTINEL, chosen_bg if chosen_bg else '\033[49m')
    return line
