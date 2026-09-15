# INFRASTRUCTURE
from p3_drag_select_regression_fixtures import (
    mod_pane, PANE_WIDTH, check, _reset_state, _capture_clipboard,
)

# FUNCTIONS

def test_col_to_index_ascii():
    print("\n[col mapping] Plain ASCII query — 1-cell-per-char boundary snapping")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    check("click before/at label end -> index 0", mod_pane._search_col_to_query_index(label_w, 'hello world') == 0)
    check("click on first char -> boundary 0 (before it)",
          mod_pane._search_col_to_query_index(label_w + 1, 'hello world') == 0)
    check("click on 7th query col -> boundary 6 (before 'w' in 'hello world')",
          mod_pane._search_col_to_query_index(label_w + 7, 'hello world') == 6)
    check("click past the end -> clamped to len(query)",
          mod_pane._search_col_to_query_index(label_w + 999, 'hello world') == len('hello world'))
    check("empty query always maps to 0", mod_pane._search_col_to_query_index(label_w + 5, '') == 0)


def test_col_to_index_wide_char():
    print("\n[col mapping] Wide-char (emoji, 2-cell) query — left/right half snapping")
    q = 'a😀b'  # a(1w) emoji(2w) b(1w)
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    # cols: label_w+1='a', label_w+2..3=emoji(2 cells), label_w+4='b'
    check("click on 'a' -> boundary 0 (before 'a')",
          mod_pane._search_col_to_query_index(label_w + 1, q) == 0)
    check("click on emoji's LEFT cell -> boundary 1 (before emoji)",
          mod_pane._search_col_to_query_index(label_w + 2, q) == 1)
    check("click on emoji's RIGHT cell -> boundary 2 (after emoji, before 'b')",
          mod_pane._search_col_to_query_index(label_w + 3, q) == 2)
    check("click on 'b' -> boundary 2 (same boundary, before 'b')",
          mod_pane._search_col_to_query_index(label_w + 4, q) == 2)
    check("click past 'b' -> boundary 3 (end of query)",
          mod_pane._search_col_to_query_index(label_w + 5, q) == 3)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label_w = len(mod_pane._SEARCH_BAR_LABEL)
        press_changed = mod_pane._handle_proxy_mouse(0, label_w + 2, 1)  # anchor at index1 ('e')
        check("press returns True (redraw)", press_changed)
        check("press focuses the bar (existing behavior preserved)", mod_pane._proxy_search.focused is True)
        check("press arms dragging", mod_pane._proxy_search.dragging is True)
        check("press sets anchor==end (empty range until motion)",
              mod_pane._proxy_search.sel_anchor == mod_pane._proxy_search.sel_end == 1)
        motion_changed = mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # extend to index6 ('w')
        check("motion returns True (redraw)", motion_changed)
        check("motion extends sel_end only, anchor unchanged",
              mod_pane._proxy_search.sel_anchor == 1 and mod_pane._proxy_search.sel_end == 6)
        release_changed = mod_pane._handle_proxy_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_pane._proxy_search.dragging is False)
        check("release copies exactly the selected substring",
              captured == ['ello '])
        check("release KEEPS the selection range visible (finished, not cleared)",
              mod_pane._proxy_search.sel_anchor == 1 and mod_pane._proxy_search.sel_end == 6)
    finally:
        mod_pane.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion — today's focus-only behavior preserved")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label_w = len(mod_pane._SEARCH_BAR_LABEL)
        mod_pane._handle_proxy_mouse(0, label_w + 3, 1)
        release_changed = mod_pane._handle_proxy_search_release()
        check("release still returns True (state changed: dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click (never clobber the real clipboard)", captured == [])
        check("selection state fully cleared after a plain click",
              mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)
        check("focus is still set (existing behavior)", mod_pane._proxy_search.focused is True)
    finally:
        mod_pane.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        changed = mod_pane._handle_proxy_search_release()
        check("release with no armed drag returns False", changed is False)
        check("no clipboard call", captured == [])
    finally:
        mod_pane.copy_to_clipboard = orig


def test_body_row_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    mod_pane.proxy_line_map[2] = ('req', 0)
    press_changed = mod_pane._handle_proxy_mouse(0, 5, 2)  # press on a body row, not row 1
    check("body-row press does not arm dragging", mod_pane._proxy_search.dragging is False)
    motion_changed = mod_pane._handle_proxy_mouse(32, 40, 2)  # motion after a body-row press
    check("motion after a body-row press falls through to generic hover (proxy_hover_row set)",
          mod_pane.proxy_hover_row == 2)
    check("search selection untouched by a body-row drag",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)


def test_click_elsewhere_clears_selection():
    print("\n[clear] Click elsewhere (body row) clears a live drag-selection")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 1, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 5, 1)
    mod_pane._handle_proxy_search_release()
    check("selection exists before the elsewhere-click",
          mod_pane._proxy_search.sel_anchor is not None)
    mod_pane.proxy_line_map[2] = ('req', 0)
    changed = mod_pane._handle_proxy_mouse(0, 5, 2)
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 1, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 5, 1)
    mod_pane._handle_proxy_search_release()
    check("selection exists before typing", mod_pane._proxy_search.sel_anchor is not None)
    changed = mod_pane._handle_proxy_search_input('x')
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)
    check("query still gets the typed char appended (typing keeps operating at the end)",
          mod_pane._proxy_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED "
          "substring (not just the last char) and clears the selection")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 2, 1)   # anchor at index1 ('e')
    mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # extend to index6 ('w') -> selects 'ello '
    mod_pane._handle_proxy_search_release()
    check("selection is 'ello ' before backspace",
          mod_pane._proxy_search.query[mod_pane._proxy_search.sel_anchor:mod_pane._proxy_search.sel_end] == 'ello ')
    changed = mod_pane._handle_proxy_search_input('\x7f')
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed (not just the last char)",
          mod_pane._proxy_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with NO active selection still trims the last "
          "char — the pre-existing single-char behavior is unaffected")
    _reset_state('hello')
    check("no selection active", mod_pane._proxy_search.sel_anchor is None)
    changed = mod_pane._handle_proxy_search_input('\x7f')
    check("backspace reports a change", changed)
    check("last char trimmed (regression: unchanged pre-existing behavior)",
          mod_pane._proxy_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (_KILL_LINE_CHAR, Cmd+Backspace hypothesis) "
          "empties the WHOLE query")
    _reset_state('some fairly long search query text')
    changed = mod_pane._handle_proxy_search_input(mod_pane._KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_pane._proxy_search.query == '')


def test_kill_line_ignores_active_selection():
    print("\n[editor-style delete] Kill-line empties the query REGARDLESS of an active "
          "selection (not selection-aware, matches standard editor Cmd+Backspace semantics)")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 2, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 7, 1)
    mod_pane._handle_proxy_search_release()
    check("selection is active before kill-line", mod_pane._proxy_search.sel_anchor is not None)
    mod_pane._handle_proxy_search_input(mod_pane._KILL_LINE_CHAR)
    check("query fully emptied (not just the selected substring)", mod_pane._proxy_search.query == '')
    check("selection also cleared", mod_pane._proxy_search.sel_anchor is None)


def test_kill_line_not_silently_swallowed_by_isprintable_fallthrough():
    print("\n[editor-style delete] \\x15 is intercepted by the kill-line branch BEFORE the "
          "isprintable() fallthrough — regression guard for the exact bug being fixed")
    check("'\\x15'.isprintable() is False (confirms the fallthrough risk this branch prevents)",
          mod_pane._KILL_LINE_CHAR.isprintable() is False)
    _reset_state('should be wiped')
    mod_pane._handle_proxy_search_input(mod_pane._KILL_LINE_CHAR)
    check("query was actually cleared, not silently ignored", mod_pane._proxy_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (any form: plain backspace, selection-delete, kill-line) never "
          "clears _proxy_search.matches — Enter remains the sole recompute trigger (confirmed: "
          "neither did the pre-existing plain-backspace/typing path)")
    _reset_state('foo')
    mod_pane._proxy_search.matches = [1, 2, 3]
    mod_pane._proxy_search.match_set = {1, 2, 3}
    mod_pane._handle_proxy_search_input('\x7f')
    check("matches survive plain backspace", mod_pane._proxy_search.matches == [1, 2, 3])
    mod_pane._proxy_search.query = 'bar'
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 1, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 3, 1)
    mod_pane._handle_proxy_search_release()
    mod_pane._handle_proxy_search_input('\x7f')
    check("matches survive selection-delete backspace", mod_pane._proxy_search.matches == [1, 2, 3])
    mod_pane._handle_proxy_search_input(mod_pane._KILL_LINE_CHAR)
    check("matches survive kill-line", mod_pane._proxy_search.matches == [1, 2, 3])


def test_esc_cancel_clears_selection():
    print("\n[clear] Esc-cancel clears a live drag-selection (alongside the query)")
    _reset_state('hello world')
    mod_pane._proxy_search.focused = True
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 1, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 5, 1)
    mod_pane._handle_proxy_search_release()
    check("selection exists before Esc", mod_pane._proxy_search.sel_anchor is not None)
    mod_pane._handle_proxy_search_cancel()
    check("selection cleared after Esc",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)
    check("query also cleared (existing Esc behavior)", mod_pane._proxy_search.query == '')


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring; "
          "no selection renders without it")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 2, 1)   # index1
    mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # index6
    mod_pane._handle_proxy_search_release()
    bar = mod_pane._render_proxy_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring",
          '\033[7mello \033[27m' in bar)

    _reset_state('hello world')  # no selection
    bar2 = mod_pane._render_proxy_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)


def test_session_change_clears_selection():
    print("\n[clear] Session change clears a live drag-selection")
    _reset_state('hello world')
    label_w = len(mod_pane._SEARCH_BAR_LABEL)
    mod_pane._handle_proxy_mouse(0, label_w + 1, 1)
    mod_pane._handle_proxy_mouse(32, label_w + 5, 1)
    mod_pane._handle_proxy_search_release()
    check("selection exists before session change", mod_pane._proxy_search.sel_anchor is not None)

    class _FakeMonitor:
        active_project_filter = None  # keeps parse_proxy_log_forwarded/find_proxy_log_path as safe no-ops
        def _get_newest_main_session(self):
            return '/tmp/pane_search_p3_fake_session'
        def _get_session_start_ts(self):
            return '2026-04-21T10:00:00Z'
        def get_main_session_files(self):
            return []

    mod_pane._proxy_current_main_session = None  # force the session-change branch to fire
    mod_pane._refresh_proxy_data(0.0, False, -9999.0, _FakeMonitor())
    check("selection cleared on session change",
          mod_pane._proxy_search.sel_anchor is None and mod_pane._proxy_search.sel_end is None)
