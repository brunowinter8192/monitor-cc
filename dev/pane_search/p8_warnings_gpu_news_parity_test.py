"""
p8_warnings_gpu_news_parity_test.py -- Regression guard for the FINAL three panes reaching
search-bar parity (rollout sub-milestones 6-8, bundled, process-docs/pane_search/): warnings
(src/panes/warnings_pane.py + warnings_render.py), gpu (src/gpu_pane/pane.py), and news
(src/news_pane/pane.py ONLY -- log_pane.py is EXCLUDED per the approved decision).

WARNINGS: 1-level expand (error_expand_states[idx]), full data always loaded. The verification
this milestone explicitly required: warnings_render.py's row-bg loop was read at line level
before assuming anything -- it ALREADY used `DIM_YELLOW_BG in line` (substring), not
`.startswith()`, so no collateral fix was needed there (unlike every prior pane). ZEBRA_BG_A==''
DOES still apply (same shared constant) -- search_bar.resolve_bg_restore is threaded into this
same (already-correct) loop. Match key is a bare int err_idx (no nesting -- one expand level).
Two-stage marking: collapsed error container-marks its whole header row; expanded ADDITIONALLY
substring-highlights the matching detail line(s). header_lines param generalizes the previously
hardcoded single-header-row offset (default 1, warnings_pane.py passes 2 for search bar +
[refresh]).

GPU + NEWS: flat, small live-fetched lists, NO scroll/viewport infra at all (pane_height is
accepted by _render_pane but never read -- confirmed by grep before implementing). Per the
approved decision: full bar mechanics (drag-select, editor-style deletion, kill-line) but
HIGHLIGHT-ONLY -- no jump-to-match. n/N still cycles current_idx (which on-screen match gets
SEARCH_CURRENT_BG vs SEARCH_MATCH_BG, and the N/M counter) with ZERO scroll call. No sentinel
needed in either pane -- neither has a per-row background/zebra/hover loop at all, so
utils.highlight_query_in_line's default restore_bg is directly correct (same simple case as the
main pane). _render_pane's OWN row numbering stays UNSHIFTED/relative to its own top in both
panes -- the search-bar row shift for _button_regions happens externally, in the loop, exactly
mirroring worker_proxy_pane's precedent -- verified by dev/click_ui/p4_gpu_news_button_probe.py
needing ZERO changes (it calls _render_pane directly).

Uses REAL src.panes.warnings_pane / warnings_render / src.gpu_pane.pane / src.news_pane.pane
functions against synthetic data -- not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p8_warnings_gpu_news_parity_test.py
"""

# INFRASTRUCTURE
import importlib
import os
import sys
from datetime import datetime
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_wpane = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_wrender = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_render')
mod_gpu = importlib.import_module(f'{_ROOT_PKG}.gpu_pane.pane')
mod_news = importlib.import_module(f'{_ROOT_PKG}.news_pane.pane')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')

PANE_WIDTH = 100
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

# Synthetic tool_errors entry
def _make_error(tool_name='Bash', worker_name='', full_text='error output', input_marker=None):
    return {
        'timestamp': '10:00:00', 'tool_name': tool_name, 'summary': full_text[:80],
        'full_text': full_text, 'worker_name': worker_name,
        'tool_call_input': {'command': input_marker} if input_marker else {},
    }


def _make_preset(name, running=True, healthy=True, port=8000, pid=123):
    return {
        'name': name, 'kind': 'preset', 'running': running, 'healthy': healthy,
        'port': port, 'pid': pid, 'rss_mb': None, 'idle_seconds': None,
        'idle_state_missing': False, 'model_name': None,
    }


# Mirrors run_gpu_loop's inline row-1/button dispatch (dev/click_ui/p4_gpu_news_button_probe.py's
# own established convention for these two panes -- mouse dispatch is inline, not a standalone
# function).
def _dispatch_gpu_click(col, row):
    if row == 1:
        return mod_search_bar.handle_search_mouse_press(mod_gpu._gpu_search, col, mod_gpu._GPU_SEARCH_BAR_LABEL)
    for (sc, ec, er), (action, target) in list(mod_gpu._button_regions.items()):
        if row == er and sc <= col <= ec:
            if action == 'refresh':
                return 'refresh'
            if target not in mod_gpu._toggle_state:
                mod_gpu._fire_button(action, target)
                return (action, target)
    return None


def _reset_warnings_state(query: str = ''):
    mod_wpane.tool_errors.clear()
    mod_wpane.error_expand_states.clear()
    mod_wpane.error_line_map.clear()
    mod_wpane.error_hover_row = None
    mod_wpane.error_scroll_offset = 0
    mod_wpane.error_copy_rows.clear()
    mod_wpane._error_copy_feedback_until.clear()
    mod_wpane._error_pane_width = PANE_WIDTH
    mod_wpane._warnings_header_regions.clear()
    mod_wpane._force_refresh = False
    mod_wpane._last_refresh_ts = 1234567890.0
    mod_wpane._warnings_search.query = query
    mod_wpane._warnings_search.focused = False
    mod_wpane._warnings_search.matches = []
    mod_wpane._warnings_search.match_set = set()
    mod_wpane._warnings_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wpane._warnings_search)


def _reset_gpu_state(query: str = ''):
    mod_gpu._button_regions.clear()
    mod_gpu._toggle_state.clear()
    mod_gpu._gpu_search.query = query
    mod_gpu._gpu_search.focused = False
    mod_gpu._gpu_search.matches = []
    mod_gpu._gpu_search.match_set = set()
    mod_gpu._gpu_search.current_idx = 0
    mod_search_bar.clear_selection(mod_gpu._gpu_search)


def _reset_news_state(query: str = ''):
    mod_news._button_regions.clear()
    mod_news._pipeline_proc = None
    mod_news._news_search.query = query
    mod_news._news_search.focused = False
    mod_news._news_search.matches = []
    mod_news._news_search.match_set = set()
    mod_news._news_search.current_idx = 0
    mod_search_bar.clear_selection(mod_news._news_search)


def _capture_clipboard(mod):
    captured = []
    orig = mod.copy_to_clipboard
    mod.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig


# ============================== WARNINGS TESTS ==============================

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
    import inspect
    # (2026-09, panes-split milestone) the zebra/hover row loop that carries this check moved out
    # of _format_warnings_pane into its own _render_warnings_rows helper — re-pointed here, same
    # assertion, same target concern.
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
    changed = mod_wpane._handle_warnings_mouse(0, 5, 20)  # unmapped body row
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
    # first_word_of_call (warnings_render's OWN pre-existing collapsed-row inline preview) shows
    # only the Bash command's FIRST WORD even when collapsed -- 'echo' here, never the marker
    # itself -- so a multi-word command is needed to prove the match was found in HIDDEN content
    # (the matcher checks the full tool_call_input value; the collapsed render does not show it).
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


# ============================== GPU TESTS ==============================

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


# ============================== NEWS TESTS ==============================

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


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P8 -- warnings + gpu + news panes search bar parity regression suite")
    print("=" * 70)

    test_warnings_state_shape()
    test_warnings_dim_yellow_bg_already_used_in_not_startswith()
    test_warnings_search_bar_row1_and_refresh_header_shifted()
    test_warnings_row1_press_focuses_and_arms_drag()
    test_warnings_drag_select_copies_to_clipboard()
    test_warnings_plain_click_no_clipboard_and_body_clears_selection()
    test_warnings_editing_mechanics()
    test_warnings_collapsed_container_mark_and_expanded_substring_mark()
    test_warnings_sentinel_resolves_to_default_bg_not_empty_string()
    test_warnings_n_N_cycles_without_touching_scroll()
    test_warnings_esc_cancel_and_reverse_video()

    test_gpu_state_shape()
    test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally()
    test_gpu_row1_click_focuses_search_bar()
    test_gpu_drag_select_and_editing()
    test_gpu_highlight_only_match_no_sentinel_needed()
    test_gpu_n_N_cycles_current_idx_no_scroll_infra()
    test_gpu_esc_cancel_bar_stays()

    test_news_state_shape()
    test_news_render_pane_stays_unshifted()
    test_news_highlight_only_match()
    test_news_drag_select_and_n_N()
    test_news_esc_cancel_bar_stays()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p8_warnings_gpu_news_parity_test_{ts}.md'
    lines = [f"# P8 warnings + gpu + news panes parity regression -- {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
