# INFRASTRUCTURE
from p8_warnings_gpu_news_parity_fixtures import (
    mod_news, mod_search_bar, mod_colors, PANE_WIDTH, check, _reset_news_state, _capture_clipboard,
)

# FUNCTIONS

def test_news_state_shape():
    print("\n[news shape] SearchState instance, lowercase label")
    check("_news_search is a search_bar.SearchState instance",
          isinstance(mod_news._news_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_news._NEWS_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_news._NEWS_SEARCH_BAR_LINES == 1)


def test_news_render_pane_stays_unshifted():
    print("\n[unshifted _render_pane] Direct call keeps row numbering relative to its own top; "
          "the external shift mirrors gpu's own pattern")
    _reset_news_state()
    status = {'doc_count': 5, 'chunk_count': 50, 'last_run_ts': '2026-01-01 00:00:00'}
    mod_news._render_pane(120, 30, status, running=False)
    unshifted_rows = sorted(er for (_sc, _ec, er) in mod_news._button_regions)
    check("[refresh] region (first inserted) is at its own top, row 1", unshifted_rows[0] == 1)
    shifted = {(sc2, ec2, er2 + mod_news._NEWS_SEARCH_BAR_LINES): v for (sc2, ec2, er2), v in mod_news._button_regions.items()}
    mod_news._button_regions.clear()
    mod_news._button_regions.update(shifted)
    shifted_rows = sorted(er for (_sc, _ec, er) in mod_news._button_regions)
    check("every region shifted by exactly _NEWS_SEARCH_BAR_LINES",
          shifted_rows == [r + mod_news._NEWS_SEARCH_BAR_LINES for r in unshifted_rows])


def test_news_highlight_only_match():
    print("\n[highlight-only] Real Enter-triggered search finds and highlights a match against "
          "the collection name (stable, independent of _is_running()'s real filesystem check)")
    _reset_news_state(mod_news.TARGET_COLLECTION)
    status = {'doc_count': 5, 'chunk_count': 50, 'last_run_ts': '2026-01-01 00:00:00'}
    mod_news._news_search_on_commit(mod_news._news_search, status)
    check("matcher found at least one match line", len(mod_news._news_search.matches) >= 1)
    current_match_line = mod_news._news_search.matches[mod_news._news_search.current_idx]
    output = mod_news._render_pane(120, 30, status, running=False,
                                    search_query=mod_news._news_search.query,
                                    search_match_line_set=mod_news._news_search.match_set,
                                    search_current_line=current_match_line)
    check("matched line is highlighted with SEARCH_CURRENT_BG",
          mod_colors.SEARCH_CURRENT_BG in output.splitlines()[current_match_line])
    check("collection name substring wrapped exactly (browser-find style)",
          f"{mod_colors.SEARCH_CURRENT_BG}{mod_news.TARGET_COLLECTION}\033[49m" in output)


def test_news_drag_select_and_n_N():
    print("\n[drag + nav] Drag-select copies exact substring; n/N cycles with no scroll infra")
    _reset_news_state('hello world')
    captured, orig = _capture_clipboard(mod_news)
    try:
        label = mod_news._NEWS_SEARCH_BAR_LABEL
        mod_search_bar.handle_search_mouse_press(mod_news._news_search, len(label) + 2, label)
        mod_search_bar.handle_search_mouse_motion(mod_news._news_search, len(label) + 7, label)
        released = mod_search_bar.handle_search_mouse_release(mod_news._news_search, mod_news.copy_to_clipboard)
        check("release copies exactly the selected substring", released and captured == ['ello '])
    finally:
        mod_news.copy_to_clipboard = orig

    _reset_news_state()
    check("no-op with zero matches", mod_news._jump_news_search_match(forward=True) is False)
    mod_news._news_search.matches = [1, 3]
    mod_news._news_search.current_idx = 0
    check("n advances to idx 1", mod_news._jump_news_search_match(forward=True) and mod_news._news_search.current_idx == 1)
    check("n wraps back to idx 0", mod_news._jump_news_search_match(forward=True) and mod_news._news_search.current_idx == 0)


def test_news_esc_cancel_bar_stays():
    print("\n[Esc] Cancel clears state; bar stays visible")
    _reset_news_state('hello world')
    mod_news._news_search.matches = [0]
    mod_news._news_search.match_set = {0}
    changed = mod_search_bar.handle_search_cancel(mod_news._news_search)
    check("cancel reports a change", changed)
    check("query/matches cleared", mod_news._news_search.query == '' and mod_news._news_search.matches == [])
    bar = mod_news._render_news_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)
