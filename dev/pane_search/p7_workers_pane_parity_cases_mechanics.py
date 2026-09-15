# INFRASTRUCTURE
from p7_workers_pane_parity_fixtures import (
    mod_wt, mod_search_bar, PANE_WIDTH, _MONITOR, check, _reset_state, _select_worker,
    _capture_clipboard,
)

# FUNCTIONS

def test_state_shape_and_label():
    print("\n[shape] Worker-tokens search state is one search_bar.SearchState, lowercase label")
    check("_worker_tokens_search is a search_bar.SearchState instance",
          isinstance(mod_wt._worker_tokens_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_wt._WT_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_wt._WT_SEARCH_BAR_LINES == 1)


def test_two_row_header_composition():
    print("\n[2-row header] Search bar row 1, worker-switch header row 2+; body rows past both")
    _reset_state()
    worker = {'name': 'w1', 'status': 'working', 'context_pct': 40}
    _select_worker('w1', [worker])
    mod_wt._worker_tokens_turns = [{
        'prompt': 'do it', 'timestamp': '2026-01-01T00:00:00Z',
        'api_calls': [{'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 10, 'content_blocks': []}],
    }]
    output, header = mod_wt._build_worker_tokens_output(_MONITOR)
    lines = header.splitlines()
    check("row 1 (search bar) contains the label", 'search:' in lines[0])
    check("row 1 has no click-arrows", '[<-]' not in lines[0] and '[->]' not in lines[0])
    check("worker-switch header text appears on a LATER line, not row 1",
          any('WORKER-TOKENS' in l for l in lines[1:]))
    check("row 1 is not a body line_map key", mod_wt.worker_tokens_line_map.get(1) is None)
    check("row 2 (worker header) is not a body line_map key either",
          mod_wt.worker_tokens_line_map.get(2) is None)
    check("header regions exist and are all on rows >= 2 (shifted past the search bar)",
          bool(mod_wt._worker_tokens_header_regions) and
          all(er >= 2 for (_sc, _ec, er) in mod_wt._worker_tokens_header_regions))
    check("all body line_map rows are past both header rows",
          all(r >= 3 for r in mod_wt.worker_tokens_line_map))


def test_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    changed = mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_wt._worker_tokens_search.focused is True)
    check("press arms dragging", mod_wt._worker_tokens_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_wt._worker_tokens_search.sel_anchor == mod_wt._worker_tokens_search.sel_end == 1)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wt._WT_SEARCH_BAR_LABEL
        mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
        motion_changed = mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
        check("motion extends sel_end only", motion_changed and mod_wt._worker_tokens_search.sel_end == 6)
        release_changed = mod_wt._handle_worker_tokens_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_wt._worker_tokens_search.dragging is False)
        check("release copies exactly the selected substring", captured == ['ello '])
    finally:
        mod_wt.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion makes zero clipboard calls")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wt._WT_SEARCH_BAR_LABEL
        mod_wt._handle_worker_tokens_mouse(0, len(label) + 3, 1, _MONITOR)
        release_changed = mod_wt._handle_worker_tokens_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
        check("selection cleared after a plain click",
              mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)
    finally:
        mod_wt.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    changed = mod_wt._handle_worker_tokens_search_release()
    check("release with no armed drag returns False", changed is False)


def test_body_click_clears_selection():
    print("\n[clear] Click on the body (row >= 3, unmapped) clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    check("selection exists before the elsewhere-click", mod_wt._worker_tokens_search.sel_anchor is not None)
    changed = mod_wt._handle_worker_tokens_mouse(0, 5, 10, _MONITOR)  # unmapped body row
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)


def test_body_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    mod_wt._handle_worker_tokens_mouse(0, 5, 10, _MONITOR)
    check("body-row press does not arm dragging", mod_wt._worker_tokens_search.dragging is False)
    mod_wt._handle_worker_tokens_mouse(32, 40, 10, _MONITOR)
    check("motion after a body-row press falls through to generic hover", mod_wt.worker_tokens_hover_row == 10)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    check("selection exists before typing", mod_wt._worker_tokens_search.sel_anchor is not None)
    changed = mod_wt._handle_worker_tokens_search_input('x')
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)
    check("typed char appended at the end", mod_wt._worker_tokens_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED substring")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    changed = mod_wt._handle_worker_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed", mod_wt._worker_tokens_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with no selection still trims the last char")
    _reset_state('hello')
    changed = mod_wt._handle_worker_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("last char trimmed", mod_wt._worker_tokens_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query")
    _reset_state('some fairly long search query text')
    changed = mod_wt._handle_worker_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_wt._worker_tokens_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (plain backspace, kill-line) never clears _worker_tokens_search.matches "
          "-- Enter remains the sole recompute trigger")
    _reset_state('foo')
    mod_wt._worker_tokens_search.matches = [(0, 0), ('turn', 1)]
    mod_wt._worker_tokens_search.match_set = {(0, 0), ('turn', 1)}
    mod_wt._handle_worker_tokens_search_input('\x7f')
    check("matches survive plain backspace", mod_wt._worker_tokens_search.matches == [(0, 0), ('turn', 1)])
    mod_wt._handle_worker_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("matches survive kill-line", mod_wt._worker_tokens_search.matches == [(0, 0), ('turn', 1)])


def test_esc_cancel_clears_state_bar_stays():
    print("\n[Esc] Cancel clears query/matches/selection; the bar itself is never hidden")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._worker_tokens_search.focused = True
    mod_wt._worker_tokens_search.matches = [(0, 0)]
    mod_wt._worker_tokens_search.match_set = {(0, 0)}
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    changed = mod_wt._handle_worker_tokens_search_cancel()
    check("cancel reports a change", changed)
    check("query cleared", mod_wt._worker_tokens_search.query == '')
    check("matches cleared", mod_wt._worker_tokens_search.matches == [] and mod_wt._worker_tokens_search.match_set == set())
    check("focused cleared", mod_wt._worker_tokens_search.focused is False)
    check("selection cleared", mod_wt._worker_tokens_search.sel_anchor is None)
    bar = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    bar = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring", '\033[7mello \033[27m' in bar)

    _reset_state('hello world')
    bar2 = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)
