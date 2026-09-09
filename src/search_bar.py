# INFRASTRUCTURE
from typing import List, Optional, Set

from .colors import RESET, WHITE, CYAN
from .utils import _cell_width, truncate_visible

# Private search-bar colors (not in the main palette — shared across every pane's search bar).
# Was duplicated per-pane (proxy_display/pane.py, core/monitor_display.py) before this module
# existed; single source now.
_SRCH_LABEL = '\033[38;2;108;112;134m'   # muted gray — the label text ("search: ", "Search: ", ...)
_SRCH_IDLE  = '\033[38;2;166;173;200m'   # medium gray — unfocused query text

# Kill-line binding (2026-08-18) — HYPOTHESIS, not confirmed: Cmd+Backspace is normally consumed
# by the terminal app itself; on macOS, Ghostty most likely maps it to the kill-line control char
# 0x15 (Ctrl-U) before it ever reaches this process. Named constant so a rebind after live
# testing (if the real captured sequence differs) is a one-line change, shared by every pane.
KILL_LINE_CHAR = '\x15'

# Placeholder a search-highlight span's restore code embeds instead of a real color — the
# embedding site (a pane's render code) doesn't know the row's eventual background (zebra/hover/
# strip/collision) at embed time; only the row-background pass does, once it runs. Looks like a
# real (if unused) SGR code so any ANSI-stripping regex already in use (utils._ANSI_ESCAPE_RE)
# strips it as zero-width wherever that already happens (padding math, truncate_visible) —
# substituted for the real per-row background via resolve_bg_restore() below.
_BG_RESTORE_SENTINEL = '\033[999m'

# FUNCTIONS

# Per-pane search bar state — one instance per pane (module-level, e.g. `_proxy_search =
# SearchState()`), replacing what used to be 8 separate globals per pane. Attributes are mutated
# in place; the reference itself is never rebound, so callers holding `state` don't need `global`
# declarations for it.
class SearchState:
    def __init__(self):
        self.query: str = ''
        self.focused: bool = False
        self.matches: List = []          # match keys, ordered — shape is pane-specific (entry_idx, event_idx, ...)
        self.match_set: Set = set()      # set(self.matches), O(1) membership
        self.current_idx: int = 0        # index into self.matches for the jump target
        # Drag-to-select (copy-only for the selection ITSELF; Backspace with a selection deletes
        # it from the query — see handle_search_input).
        self.dragging: bool = False       # True between a row-1 press and its matching release
        self.sel_anchor: Optional[int] = None  # char-boundary index [0, len(query)] where drag started
        self.sel_end: Optional[int] = None     # char-boundary index of the current/last drag position

# Clear the drag-select highlight/state only — never touches state.query. Shared by
# click-elsewhere, new-input, Esc-cancel, and session-change across every pane.
def clear_selection(state: SearchState) -> None:
    state.dragging = False
    state.sel_anchor = None
    state.sel_end = None

# Reset a search bar back to its empty, unfocused, no-matches state (Esc-cancel / session-change
# semantics — identical across every pane per the rollout's design). Returns True (always a
# redraw).
def handle_search_cancel(state: SearchState) -> bool:
    state.focused = False
    state.query = ''
    state.matches = []
    state.match_set = set()
    clear_selection(state)
    return True

# Handle keyboard input while a search bar is focused; returns True if input_changed.
# on_commit(state): pane-supplied — runs the actual (pane-specific) search and jumps to the
# first match if any; called on Enter, AFTER which this function unfocuses the bar. Editing
# NEVER clears state.matches/match_set on its own (confirmed against the proxy pane's
# pre-existing behavior, 2026-08-18: neither did plain backspace/typing) — Enter (on_commit) is
# the only recompute trigger.
def handle_search_input(state: SearchState, char: str, on_commit, kill_line_char: str = KILL_LINE_CHAR, max_len: int = 200) -> bool:
    # Any new input clears a lingering drag-selection highlight — capture its (start, end) range
    # BEFORE clearing so Backspace can still delete it, and track whether one existed so an
    # otherwise-unhandled char (e.g. a stray control character) still triggers the redraw that
    # makes the highlight disappear, instead of silently mutating state with no repaint.
    had_selection = state.sel_anchor is not None
    sel_range = None
    if state.sel_anchor is not None and state.sel_end is not None:
        s, e = sorted((state.sel_anchor, state.sel_end))
        if s != e:
            sel_range = (s, e)
    clear_selection(state)
    if char == kill_line_char:  # Cmd+Backspace hypothesis — kill the whole line
        state.query = ''
        return True
    if char in ('\x7f', '\x08'):  # backspace (DEL or BS)
        if sel_range is not None:
            s, e = sel_range
            state.query = state.query[:s] + state.query[e:]
        else:
            state.query = state.query[:-1]
        return True
    if char in ('\r', '\n'):  # Enter → (re)run search via the pane's own callback, unfocus
        on_commit(state)
        state.focused = False
        return True
    if char.isprintable():
        if len(state.query) < max_len:
            state.query += char
            return True
    return had_selection

# Map a 1-based screen column to a char-BOUNDARY index [0, len(query)] into the query text (a
# "cursor position", not a character index — needed so a click on the right half of a 2-wide
# char snaps to AFTER it, not before). label is the bar's own leading text ("search: ",
# "Search: ", ...) — pure ASCII in every pane so far, so its own width is just its char count.
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

# Row-1 press: focuses the bar AND anchors a potential drag-select at the clicked column.
# Returns True (always a redraw) — mirrors the pre-extraction behavior where a plain click
# (press+release, no motion) still focuses even though no drag results.
def handle_search_mouse_press(state: SearchState, col: int, label: str) -> bool:
    state.focused = True
    idx = col_to_query_index(col, state.query, label)
    state.sel_anchor = idx
    state.sel_end = idx
    state.dragging = True
    return True

# Motion with the left button held (SGR button 32, the 0+32 flag) while a row-1 drag is active —
# caller gates this on state.dragging before calling (mirrors a body-row drag never reaching
# here since state.dragging is only set True by handle_search_mouse_press). Updates sel_end only;
# the caller does not need to pass row — dragging clamps vertical drift to the bar's own column
# model by construction (nothing here reads row at all).
def handle_search_mouse_motion(state: SearchState, col: int, label: str) -> bool:
    state.sel_end = col_to_query_index(col, state.query, label)
    return True

# Finalize a row-1 drag on SGR mouse release; returns True if a redraw is needed. No-op (False)
# unless a row-1 drag was actually in progress — safe to call unconditionally on EVERY release
# sentinel from any pane, including releases after a plain click elsewhere (never armed).
# copy_to_clipboard_fn is INJECTED (not imported directly) rather than a fixed import — each
# pane passes ITS OWN `copy_to_clipboard` name (re-exported from input.click_handler at the
# call site), so a pane-level monkeypatch of that name (the existing test convention throughout
# this codebase, e.g. dev/click_ui's copy-click probes) still intercepts calls made through this
# shared function, exactly as it would have before this mechanic was extracted.
def handle_search_mouse_release(state: SearchState, copy_to_clipboard_fn) -> bool:
    if not state.dragging:
        return False
    state.dragging = False
    if state.sel_anchor is None or state.sel_end is None:
        return False
    start, end = sorted((state.sel_anchor, state.sel_end))
    if start == end:
        # Plain click, no motion in between — keeps "focus only" behavior. No clipboard call
        # (never clobber the user's real clipboard with an empty string).
        clear_selection(state)
        return True
    copy_to_clipboard_fn(state.query[start:end])
    return True

# Render the always-visible search bar (row 1): "<label><query>_" left, "N/M" match counter
# right. A live/finished drag-selection renders in SGR reverse-video (terminal convention for
# text selection, distinct from any pane's own color palette). show_counter=False for a pane
# that doesn't want the N/M counter (e.g. jump-to-match-less panes). Returns an ANSI string
# truncated to pane_width visible cells.
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

# Substitute every _BG_RESTORE_SENTINEL occurrence in line for the row's real background
# (chosen_bg). chosen_bg == '' (a "no override" zebra variant) must resolve to an explicit
# default-background reset ('\033[49m'), NOT the empty string itself — substituting '' would
# DELETE the sentinel outright, leaving a search-highlight background active with nothing to
# close it before the row's own trailing erase-to-EOL, flooding the rest of the row with the
# highlight color (2026-08-18 live bug on the proxy pane, reproduced byte-for-byte — see
# process-docs/pane_search/). No-op when the sentinel isn't present in the line.
def resolve_bg_restore(line: str, chosen_bg: str) -> str:
    if _BG_RESTORE_SENTINEL in line:
        return line.replace(_BG_RESTORE_SENTINEL, chosen_bg if chosen_bg else '\033[49m')
    return line
