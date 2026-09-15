# INFRASTRUCTURE
from p5_worker_proxy_pane_parity_fixtures import (
    mod_wp, mod_search_bar, PANE_WIDTH, check, _make_wp_entry, _reset_state, _click,
    _capture_clipboard, _build_output_with_worker,
)

# FUNCTIONS

def test_state_shape():
    print("\n[shape] Worker-proxy search state is one search_bar.SearchState, lowercase label")
    check("_worker_proxy_search is a search_bar.SearchState instance",
          isinstance(mod_wp._worker_proxy_search, mod_search_bar.SearchState))
    check("label matches the proxy pane's ('search: ', this pane's structural twin)",
          mod_wp._WP_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_wp._WP_SEARCH_BAR_LINES == 1)


def test_two_row_header_composition_and_shifts():
    print("\n[2-row header] Search bar row 1, worker-switcher header shifted to row 2+; "
          "header_regions and line_map both account for the search bar row")
    _reset_state()
    mod_wp._worker_proxy_workers = [{'name': 'alpha', 'session': ''}, {'name': 'beta', 'session': ''}]
    mod_wp.worker_proxy_entries.extend(_make_wp_entry(i) for i in range(3))
    output, header = _build_output_with_worker('alpha')
    lines = header.splitlines()
    check("row 1 (search bar) contains the label", 'search:' in lines[0])
    check("row 1 has no click-arrows", '[<-]' not in lines[0] and '[->]' not in lines[0]
          and '[←]' not in lines[0] and '[→]' not in lines[0])
    check("worker-switcher header text appears on a LATER line, not row 1",
          any('WORKER-PROXY' in l for l in lines[1:]))
    check("row 1 is not a body line_map key", mod_wp.worker_proxy_line_map.get(1) is None)
    check("row 2 (worker header) is not a body line_map key either",
          mod_wp.worker_proxy_line_map.get(2) is None)
    check("all header-region rows are >= 2 (shifted past the search bar row)",
          bool(mod_wp._worker_proxy_header_regions) and
          all(er >= 2 for (_sc, _ec, er) in mod_wp._worker_proxy_header_regions))
    check("all body line_map rows are past BOTH header rows (search bar + 1-line worker header)",
          all(r >= 3 for r in mod_wp.worker_proxy_line_map))


def test_header_marker_click_still_selects_worker_at_shifted_row():
    print("\n[header click] A click on the (now row-2+) worker marker still selects that worker")
    _reset_state()
    mod_wp._worker_proxy_workers = [{'name': 'alpha', 'session': ''}]
    mod_wp.worker_proxy_entries.extend(_make_wp_entry(i) for i in range(2))
    _build_output_with_worker('alpha')
    check("region exists and is at a shifted (>=2) row", bool(mod_wp._worker_proxy_header_regions))
    (sc, ec, er), name = next(iter(mod_wp._worker_proxy_header_regions.items()))
    check("marker region row is 2 (single-line worker header, right after the search bar)", er == 2)
    captured = []
    orig_write_selection = mod_wp.write_selection
    mod_wp.write_selection = lambda pf, n: captured.append(n)
    try:
        changed = _click(0, sc, er)
    finally:
        mod_wp.write_selection = orig_write_selection
    check("header-marker click at the shifted row selects the worker", changed and captured == [name])
    check("force_reload set", mod_wp._worker_proxy_force_reload is True)


def test_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    changed = _click(0, len(label) + 2, 1)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_wp._worker_proxy_search.focused is True)
    check("press arms dragging", mod_wp._worker_proxy_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_wp._worker_proxy_search.sel_anchor == mod_wp._worker_proxy_search.sel_end == 1)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wp._WP_SEARCH_BAR_LABEL
        _click(0, len(label) + 2, 1)
        motion_changed = _click(32, len(label) + 7, 1)
        check("motion extends sel_end only", motion_changed and mod_wp._worker_proxy_search.sel_end == 6)
        release_changed = mod_wp._handle_worker_proxy_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_wp._worker_proxy_search.dragging is False)
        check("release copies exactly the selected substring", captured == ['ello '])
    finally:
        mod_wp.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion makes zero clipboard calls")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wp._WP_SEARCH_BAR_LABEL
        _click(0, len(label) + 3, 1)
        release_changed = mod_wp._handle_worker_proxy_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
        check("selection cleared after a plain click",
              mod_wp._worker_proxy_search.sel_anchor is None and mod_wp._worker_proxy_search.sel_end is None)
    finally:
        mod_wp.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    changed = mod_wp._handle_worker_proxy_search_release()
    check("release with no armed drag returns False", changed is False)


def test_body_row_click_clears_selection():
    print("\n[clear] Click on the buffer area (row >= 2, unmapped) clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    _click(0, len(label) + 1, 1)
    _click(32, len(label) + 5, 1)
    mod_wp._handle_worker_proxy_search_release()
    check("selection exists before the elsewhere-click", mod_wp._worker_proxy_search.sel_anchor is not None)
    changed = _click(0, 5, 10)  # unmapped body row, no header regions registered
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_wp._worker_proxy_search.sel_anchor is None and mod_wp._worker_proxy_search.sel_end is None)


def test_body_row_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    _click(0, 5, 10)
    check("body-row press does not arm dragging", mod_wp._worker_proxy_search.dragging is False)
    _click(32, 40, 10)
    check("motion after a body-row press falls through to generic hover", mod_wp.worker_proxy_hover_row == 10)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    _click(0, len(label) + 1, 1)
    _click(32, len(label) + 5, 1)
    mod_wp._handle_worker_proxy_search_release()
    check("selection exists before typing", mod_wp._worker_proxy_search.sel_anchor is not None)
    changed = mod_wp._handle_worker_proxy_search_input('x')
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_wp._worker_proxy_search.sel_anchor is None and mod_wp._worker_proxy_search.sel_end is None)
    check("typed char appended at the end", mod_wp._worker_proxy_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED substring")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    _click(0, len(label) + 2, 1)
    _click(32, len(label) + 7, 1)
    mod_wp._handle_worker_proxy_search_release()
    changed = mod_wp._handle_worker_proxy_search_input('\x7f')
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed", mod_wp._worker_proxy_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_wp._worker_proxy_search.sel_anchor is None and mod_wp._worker_proxy_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with no selection still trims the last char")
    _reset_state('hello')
    changed = mod_wp._handle_worker_proxy_search_input('\x7f')
    check("backspace reports a change", changed)
    check("last char trimmed", mod_wp._worker_proxy_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query")
    _reset_state('some fairly long search query text')
    changed = mod_wp._handle_worker_proxy_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_wp._worker_proxy_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (plain backspace, selection-delete, kill-line) never clears "
          "_worker_proxy_search.matches — Enter remains the sole recompute trigger")
    _reset_state('foo')
    mod_wp._worker_proxy_search.matches = [1, 2, 3]
    mod_wp._worker_proxy_search.match_set = {1, 2, 3}
    mod_wp._handle_worker_proxy_search_input('\x7f')
    check("matches survive plain backspace", mod_wp._worker_proxy_search.matches == [1, 2, 3])
    mod_wp._handle_worker_proxy_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("matches survive kill-line", mod_wp._worker_proxy_search.matches == [1, 2, 3])


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    _click(0, len(label) + 2, 1)
    _click(32, len(label) + 7, 1)
    mod_wp._handle_worker_proxy_search_release()
    bar = mod_wp._render_worker_proxy_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring", '\033[7mello \033[27m' in bar)

    _reset_state('hello world')
    bar2 = mod_wp._render_worker_proxy_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)
