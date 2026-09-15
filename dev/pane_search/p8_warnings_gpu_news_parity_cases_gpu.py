# INFRASTRUCTURE
from p8_warnings_gpu_news_parity_fixtures import (
    mod_gpu, mod_search_bar, mod_colors, PANE_WIDTH,
    check, _make_preset, _dispatch_gpu_click, _reset_gpu_state, _capture_clipboard,
)

# FUNCTIONS

def test_gpu_state_shape():
    print("\n[gpu shape] SearchState instance, lowercase label, no scroll infra confirmed")
    check("_gpu_search is a search_bar.SearchState instance",
          isinstance(mod_gpu._gpu_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_gpu._GPU_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_gpu._GPU_SEARCH_BAR_LINES == 1)


def test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally():
    print("\n[unshifted _render_pane] Direct call keeps row numbering relative to its own top "
          "(mirrors gpu_news_button_probe's own direct-call convention, needed zero changes); "
          "the search-bar row shift happens externally, in the loop")
    _reset_gpu_state()
    presets = [_make_preset('alpha')]
    mod_gpu._render_pane(PANE_WIDTH, 30, presets, [], [], [], {}, [])
    (sc, ec, er) = next(iter(mod_gpu._button_regions))
    check("direct _render_pane call registers its own header region at row 1 (its own top)", er == 1)
    # Replicate run_gpu_loop's own external shift snippet
    shifted = {(sc2, ec2, er2 + mod_gpu._GPU_SEARCH_BAR_LINES): v for (sc2, ec2, er2), v in mod_gpu._button_regions.items()}
    mod_gpu._button_regions.clear()
    mod_gpu._button_regions.update(shifted)
    (sc3, ec3, er3) = next(iter(mod_gpu._button_regions))
    check("after the external shift, the region is at row 2", er3 == 1 + mod_gpu._GPU_SEARCH_BAR_LINES)
    result = _dispatch_gpu_click((sc3 + ec3) // 2, er3)
    check("a click at the shifted row still correctly dispatches to 'refresh'", result == 'refresh')


def test_gpu_row1_click_focuses_search_bar():
    print("\n[press] A row-1 click (inline dispatch) focuses the bar")
    _reset_gpu_state('hello world')
    label = mod_gpu._GPU_SEARCH_BAR_LABEL
    result = _dispatch_gpu_click(len(label) + 2, 1)
    check("row-1 dispatch returns True (search_bar handled it)", result is True)
    check("press focuses the bar", mod_gpu._gpu_search.focused is True)
    check("press arms dragging", mod_gpu._gpu_search.dragging is True)


def test_gpu_drag_select_and_editing():
    print("\n[drag + editing] press -> motion -> release copies the substring; editing mechanics")
    _reset_gpu_state('hello world')
    captured, orig = _capture_clipboard(mod_gpu)
    try:
        label = mod_gpu._GPU_SEARCH_BAR_LABEL
        mod_search_bar.handle_search_mouse_press(mod_gpu._gpu_search, len(label) + 2, label)
        mod_search_bar.handle_search_mouse_motion(mod_gpu._gpu_search, len(label) + 7, label)
        released = mod_search_bar.handle_search_mouse_release(mod_gpu._gpu_search, mod_gpu.copy_to_clipboard)
        check("release copies exactly the selected substring", released and captured == ['ello '])
    finally:
        mod_gpu.copy_to_clipboard = orig

    _reset_gpu_state('hello')
    mod_search_bar.handle_search_input(mod_gpu._gpu_search, '\x7f', on_commit=lambda s: None)
    check("plain backspace trims last char", mod_gpu._gpu_search.query == 'hell')

    _reset_gpu_state('some long query')
    mod_search_bar.handle_search_input(mod_gpu._gpu_search, mod_search_bar.KILL_LINE_CHAR, on_commit=lambda s: None)
    check("kill-line empties the query", mod_gpu._gpu_search.query == '')


def test_gpu_highlight_only_match_no_sentinel_needed():
    print("\n[highlight-only] Real Enter-triggered search finds and highlights a match; NO "
          "sentinel machinery involved (this pane has no per-row background at all)")
    _reset_gpu_state('unique_preset_marker')
    presets = [_make_preset('unique_preset_marker')]
    mod_gpu._gpu_search_on_commit(mod_gpu._gpu_search, presets, [], [], [], {}, [])
    check("matcher found at least one match line", len(mod_gpu._gpu_search.matches) >= 1)
    current_match_line = mod_gpu._gpu_search.matches[mod_gpu._gpu_search.current_idx]
    output = mod_gpu._render_pane(PANE_WIDTH, 30, presets, [], [], [], {}, [],
                                   search_query=mod_gpu._gpu_search.query,
                                   search_match_line_set=mod_gpu._gpu_search.match_set,
                                   search_current_line=current_match_line)
    check("matched line is highlighted with SEARCH_CURRENT_BG",
          mod_colors.SEARCH_CURRENT_BG in output.splitlines()[current_match_line])
    check("the query substring itself is wrapped exactly (browser-find style)",
          f"{mod_colors.SEARCH_CURRENT_BG}unique_preset_marker\033[49m" in output)


def test_gpu_n_N_cycles_current_idx_no_scroll_infra():
    print("\n[nav, no scroll] n/N cycles current_idx with zero scroll call -- this pane has no "
          "scroll/viewport infra at all")
    _reset_gpu_state()
    check("no-op with zero matches", mod_gpu._jump_gpu_search_match(forward=True) is False)
    mod_gpu._gpu_search.matches = [2, 5, 9]
    mod_gpu._gpu_search.current_idx = 0
    check("n advances to idx 1", mod_gpu._jump_gpu_search_match(forward=True) and mod_gpu._gpu_search.current_idx == 1)
    check("n advances to idx 2", mod_gpu._jump_gpu_search_match(forward=True) and mod_gpu._gpu_search.current_idx == 2)
    check("n wraps back to idx 0", mod_gpu._jump_gpu_search_match(forward=True) and mod_gpu._gpu_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_gpu._jump_gpu_search_match(forward=False) and mod_gpu._gpu_search.current_idx == 2)


def test_gpu_esc_cancel_bar_stays():
    print("\n[Esc] Cancel clears state; bar stays visible")
    _reset_gpu_state('hello world')
    mod_gpu._gpu_search.matches = [0]
    mod_gpu._gpu_search.match_set = {0}
    changed = mod_search_bar.handle_search_cancel(mod_gpu._gpu_search)
    check("cancel reports a change", changed)
    check("query/matches cleared", mod_gpu._gpu_search.query == '' and mod_gpu._gpu_search.matches == [])
    bar = mod_gpu._render_gpu_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)
