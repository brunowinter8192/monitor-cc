# INFRASTRUCTURE
import inspect

from p8_warnings_gpu_news_parity_fixtures import (
    mod_wpane, mod_wrender, mod_search_bar, mod_colors, PANE_WIDTH,
    check, _make_error, _reset_warnings_state, _capture_clipboard,
)

# FUNCTIONS

def test_warnings_state_shape():
    print("\n[warnings shape] SearchState instance, lowercase label, header_lines composition")
    check("_warnings_search is a search_bar.SearchState instance",
          isinstance(mod_wpane._warnings_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_wpane._WARNINGS_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_wpane._WARNINGS_SEARCH_BAR_LINES == 1)


def test_warnings_dim_yellow_bg_already_used_in_not_startswith():
    print("\n[verification] warnings_render.py's pre-existing DIM_YELLOW_BG detection already "
          "uses 'in line', not '.startswith()' -- confirmed by reading the source directly, "
          "no collateral fix needed here (unlike token_pane/worker_pane)")
    src = inspect.getsource(mod_wrender._render_warnings_rows)
    check("source contains 'DIM_YELLOW_BG in line' (substring form)",
          'DIM_YELLOW_BG in line' in src)
    check("source does NOT contain a '.startswith(DIM_YELLOW_BG)' call",
          '.startswith(DIM_YELLOW_BG)' not in src)


def test_warnings_search_bar_row1_and_refresh_header_shifted():
    print("\n[2-row header] Search bar row 1; [refresh] region shifted to row 2")
    _reset_warnings_state()
    output, header = mod_wpane._build_warnings_output()
    first_line = header.splitlines()[0]
    check("row 1 shows the 'search: ' label", 'search:' in first_line)
    check("no click-arrows", '[←]' not in first_line and '[→]' not in first_line)
    regions = dict(mod_wpane._warnings_header_regions)
    check("[refresh] region exists and is at row 2 (shifted past the search bar)",
          bool(regions) and next(iter(regions))[2] == 1 + mod_wpane._WARNINGS_SEARCH_BAR_LINES)
    (sc, ec, er) = next(iter(regions))
    changed = mod_wpane._handle_warnings_mouse(0, (sc + ec) // 2, er)
    check("clicking the shifted [refresh] region still sets _force_refresh", changed and mod_wpane._force_refresh)


def test_warnings_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_warnings_state('hello world')
    label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
    changed = mod_wpane._handle_warnings_mouse(0, len(label) + 2, 1)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_wpane._warnings_search.focused is True)
    check("press arms dragging", mod_wpane._warnings_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_wpane._warnings_search.sel_anchor == mod_wpane._warnings_search.sel_end == 1)


def test_warnings_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_warnings_state('hello world')
    captured, orig = _capture_clipboard(mod_wpane)
    try:
        label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
        mod_wpane._handle_warnings_mouse(0, len(label) + 2, 1)
        motion_changed = mod_wpane._handle_warnings_mouse(32, len(label) + 7, 1)
        check("motion extends sel_end only", motion_changed and mod_wpane._warnings_search.sel_end == 6)
        release_changed = mod_wpane._handle_warnings_search_release()
        check("release copies exactly the selected substring", release_changed and captured == ['ello '])
    finally:
        mod_wpane.copy_to_clipboard = orig


def test_warnings_plain_click_no_clipboard_and_body_clears_selection():
    print("\n[plain click / body clear] No motion -> zero clipboard calls; body click clears selection")
    _reset_warnings_state('hello world')
    captured, orig = _capture_clipboard(mod_wpane)
    try:
        label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
        mod_wpane._handle_warnings_mouse(0, len(label) + 3, 1)
        release_changed = mod_wpane._handle_warnings_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
    finally:
        mod_wpane.copy_to_clipboard = orig
    _reset_warnings_state('hello world')
    label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
    mod_wpane._handle_warnings_mouse(0, len(label) + 1, 1)
    mod_wpane._handle_warnings_mouse(32, len(label) + 5, 1)
    mod_wpane._handle_warnings_search_release()
    changed = mod_wpane._handle_warnings_mouse(0, 5, 20)
    check("elsewhere-click clears the selection (reports a change)", changed)
    check("selection actually cleared",
          mod_wpane._warnings_search.sel_anchor is None and mod_wpane._warnings_search.sel_end is None)


def test_warnings_editing_mechanics():
    print("\n[editing] Backspace-selection-delete, plain backspace, kill-line, matches survive editing")
    _reset_warnings_state('hello world')
    label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
    mod_wpane._handle_warnings_mouse(0, len(label) + 2, 1)
    mod_wpane._handle_warnings_mouse(32, len(label) + 7, 1)
    mod_wpane._handle_warnings_search_release()
    mod_wpane._handle_warnings_search_input('\x7f')
    check("selection-delete removed 'ello '", mod_wpane._warnings_search.query == 'hworld')

    _reset_warnings_state('hello')
    mod_wpane._handle_warnings_search_input('\x7f')
    check("plain backspace trims last char", mod_wpane._warnings_search.query == 'hell')

    _reset_warnings_state('some long query')
    mod_wpane._handle_warnings_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("kill-line empties the query", mod_wpane._warnings_search.query == '')

    _reset_warnings_state('foo')
    mod_wpane._warnings_search.matches = [0, 1]
    mod_wpane._warnings_search.match_set = {0, 1}
    mod_wpane._handle_warnings_search_input('\x7f')
    check("matches survive plain backspace", mod_wpane._warnings_search.matches == [0, 1])


def test_warnings_collapsed_container_mark_and_expanded_substring_mark():
    print("\n[two-stage match] Collapsed error container-marks its header row; expanded "
          "ADDITIONALLY substring-highlights the matching detail line")
    _reset_warnings_state('unique_marker_x')
    mod_wpane.tool_errors.append(_make_error(input_marker='echo unique_marker_x'))
    check("error is NOT expanded", mod_wpane.error_expand_states.get(0, False) is False)
    changed = mod_wpane._handle_warnings_search_input('\r')
    check("Enter reports a change", changed)
    check("real search found the error", mod_wpane._warnings_search.matches == [0])
    output, _ = mod_wpane._build_warnings_output()
    row = next(r for r, idx in mod_wpane.error_line_map.items() if idx == 0)
    header_line = output.splitlines()[row - 1]
    check("collapsed header line is container-marked", mod_colors.SEARCH_CURRENT_BG in header_line)
    check("the marker text itself does NOT leak into the collapsed row (only 'echo' shows)",
          'unique_marker_x' not in header_line)

    mod_wpane.error_expand_states[0] = True
    output2, _ = mod_wpane._build_warnings_output()
    check("header line STILL container-marked when expanded", mod_colors.SEARCH_CURRENT_BG in output2)
    check("the matched substring itself is browser-find highlighted",
          f"{mod_colors.SEARCH_CURRENT_BG}unique_marker_x\033[49m" in output2)
    check("no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output",
          mod_search_bar._BG_RESTORE_SENTINEL not in output2)


def test_warnings_sentinel_resolves_to_default_bg_not_empty_string():
    print("\n[sentinel fix] ZEBRA_BG_A=='' applies here too -- an explicit \\033[49m must appear "
          "after a highlighted detail line, not a raw leaked sentinel")
    check("ZEBRA_BG_A is indeed the empty string", mod_colors.ZEBRA_BG_A == '')
    _reset_warnings_state('unique_marker_z')
    mod_wpane.tool_errors.append(_make_error(input_marker='unique_marker_z'))
    mod_wpane.error_expand_states[0] = True
    mod_wpane._handle_warnings_search_input('\r')
    output, _ = mod_wpane._build_warnings_output()
    check("an explicit \\033[49m appears right after the highlighted detail-line text",
          "unique_marker_z\033[49m" in output)
    check("no raw _BG_RESTORE_SENTINEL leaked", mod_search_bar._BG_RESTORE_SENTINEL not in output)


def test_warnings_n_N_cycles_without_touching_scroll():
    print("\n[nav] n/N cycles current_idx (this pane HAS real scroll infra, but n/N deliberately "
          "never touches error_scroll_offset -- only cycles which match is 'current')")
    _reset_warnings_state()
    check("no-op with zero matches", mod_wpane._jump_warnings_search_match(forward=True) is False)
    mod_wpane._warnings_search.matches = [0, 1, 2]
    mod_wpane._warnings_search.current_idx = 0
    mod_wpane.error_scroll_offset = 5
    check("n advances to idx 1", mod_wpane._jump_warnings_search_match(forward=True) and mod_wpane._warnings_search.current_idx == 1)
    check("n advances to idx 2", mod_wpane._jump_warnings_search_match(forward=True) and mod_wpane._warnings_search.current_idx == 2)
    check("n wraps back to idx 0", mod_wpane._jump_warnings_search_match(forward=True) and mod_wpane._warnings_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_wpane._jump_warnings_search_match(forward=False) and mod_wpane._warnings_search.current_idx == 2)
    check("error_scroll_offset untouched by n/N", mod_wpane.error_scroll_offset == 5)


def test_warnings_esc_cancel_and_reverse_video():
    print("\n[Esc + render] Cancel clears state, bar stays visible; drag-select renders reverse-video")
    _reset_warnings_state('hello world')
    label = mod_wpane._WARNINGS_SEARCH_BAR_LABEL
    mod_wpane._warnings_search.focused = True
    mod_wpane._warnings_search.matches = [0]
    mod_wpane._warnings_search.match_set = {0}
    mod_wpane._handle_warnings_mouse(0, len(label) + 1, 1)
    mod_wpane._handle_warnings_mouse(32, len(label) + 5, 1)
    mod_wpane._handle_warnings_search_release()
    changed = mod_wpane._handle_warnings_search_cancel()
    check("cancel reports a change", changed)
    check("query/matches/selection cleared",
          mod_wpane._warnings_search.query == '' and mod_wpane._warnings_search.matches == []
          and mod_wpane._warnings_search.sel_anchor is None)
    bar = mod_wpane._render_warnings_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)

    _reset_warnings_state('hello world')
    mod_wpane._handle_warnings_mouse(0, len(label) + 2, 1)
    mod_wpane._handle_warnings_mouse(32, len(label) + 7, 1)
    mod_wpane._handle_warnings_search_release()
    bar2 = mod_wpane._render_warnings_search_bar(PANE_WIDTH)
    check("reverse-video wraps exactly the selected substring", '\033[7mello \033[27m' in bar2)
