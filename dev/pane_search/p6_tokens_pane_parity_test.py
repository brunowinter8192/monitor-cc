"""
p6_tokens_pane_parity_test.py — Regression guard for the tokens pane's search bar reaching
parity with the proxy pane (rollout sub-milestone 4, process-docs/pane_search/).

token_pane.py is structurally simpler than the proxy family: single expand level
(cache_expand_states[(turn_idx, call_idx)], turns themselves never collapse), data ALWAYS
fully loaded incrementally (no windowing, no reconstruction step — on_commit just builds
matches over what's in memory via token_search.build_token_search_matches). Three genuinely
new pieces this milestone had to build:

  - THE SENTINEL BUG, SAME CLASS AS THE PROXY PANE: ZEBRA_BG_A == '' (confirmed in
    constants.py) is the chosen_bg for every non-hovered/non-error row and every detail line.
    Search highlights are embedded with search_bar._BG_RESTORE_SENTINEL at construction time
    (token_format.py) and resolved via search_bar.resolve_bg_restore(line, chosen_bg) in
    token_pane.py's own hand-rolled row loop, right after chosen_bg is chosen — exact same
    fix shape as process-docs/pane_search/2026-08-18_highlight_flood_empty_bg_fix.md.
  - 2-ROW HEADER: format_cache_tracker's optional sticky_header (row 1 when scrolled, before
    this milestone) now shifts to row 2 — the search bar (_TOKENS_SEARCH_BAR_LINES=1, fixed)
    always wins row 1. format_cache_tracker's own internal viewport reservation (-1, for the
    sticky-header slot) is UNTOUCHED; _build_tokens_output now passes pane_height -
    _TOKENS_SEARCH_BAR_LINES as format_cache_tracker's own pane_height argument instead.
  - TWO-KEY MATCH SEMANTICS: a match key is either (turn_idx, call_idx) [found in that call's
    own header or force-expanded detail content] or ('turn', turn_idx) [found in the turn's
    own prompt/timestamp line — turns have no expand state]. BOTH get an UNCONDITIONAL
    whole-line "container mark" (not a literal-substring-only wrap) regardless of expand
    state — mirrors proxy's REQ-header "text extent" marking, since the actual matching text
    may be buried in unrendered (collapsed) detail. An EXPANDED matching call additionally
    gets its specific matching detail line(s) browser-find substring-highlighted. ('turn', idx)
    keys are deliberately kept OUT of line_keys/cache_line_map (turn headers stay
    non-interactive for clicks, exactly as before) — see format_cache_tracker's new nav_out
    param, populated separately for jump-to-match scroll math only.

format_cache_tracker's signature grew (search_match_set/search_current_key/search_query/
nav_out, all optional, all default to a no-op) WITHOUT changing its return arity — verified
byte-identical against all 4 real callers (token_pane.py, workers/worker_format.py,
dev/click_ui/p2_copy_click_probe.py, dev/display/A_format_cache_tracker_proof.py) via a
frozen-turns old-vs-new comparison (the live dev/display/A_format_cache_tracker_proof.py
harness reads directly from ~/.claude/projects/.../*.jsonl — the top-10-most-recently-modified
REAL session files — which turned out to be actively growing during this session, producing a
false-positive mismatch on a naive capture-then-verify-later run; the frozen-snapshot
comparison, held constant across both code versions in the same process, is the reliable
evidence and is not re-run here — see process-docs/pane_search/ for the full writeup).

Uses REAL src.panes.token_pane / src.format.token_format / src.panes.token_search functions
against synthetic turns — not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p6_tokens_pane_parity_test.py
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
mod_tp = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
mod_ts = importlib.import_module(f'{_ROOT_PKG}.panes.token_search')
mod_tf = importlib.import_module(f'{_ROOT_PKG}.format.token_format')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')
mod_monitor = importlib.import_module(f'{_ROOT_PKG}.core.monitor')
mod_parser = importlib.import_module(f'{_ROOT_PKG}.proxy_display.parser')
mod_side_logs = importlib.import_module(f'{_ROOT_PKG}.proxy_display.side_logs')

PANE_WIDTH = 100
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

# Synthetic turn — one call, optionally carrying a marker in its own prompt (turn-level match
# surface) and/or a content_blocks text preview (call-level match surface, only found by the
# matcher's force-expand, invisible when collapsed in a real render).
def _make_turn(idx: int, prompt_marker: str = None, call_marker: str = None,
                cache_read: int = 1000, cache_creation: int = 0) -> dict:
    prompt = f"turn {idx}" + (f" {prompt_marker}" if prompt_marker else "")
    content_blocks = [{'type': 'text', 'preview': call_marker, 'chars': len(call_marker)}] if call_marker else []
    call = {
        'cache_read': cache_read, 'cache_creation': cache_creation, 'direct': 0, 'output_tokens': 50,
        'content_blocks': content_blocks,
    }
    return {'prompt': prompt, 'timestamp': f'2026-01-01T00:{idx:02d}:00Z', 'api_calls': [call]}


def _reset_state(query: str = ''):
    mod_tp.cache_expand_states.clear()
    mod_tp.cache_line_map.clear()
    mod_tp.cache_hover_row = None
    mod_tp.cache_scroll_offset = 0
    mod_tp.cache_copy_rows.clear()
    mod_tp._cache_copy_feedback_until.clear()
    mod_tp._cache_pane_width = PANE_WIDTH
    mod_tp._cache_turns.clear()
    mod_tp._cache_current_filepath = None
    mod_tp._tokens_nav.clear()
    mod_tp._tokens_search.query = query
    mod_tp._tokens_search.focused = False
    mod_tp._tokens_search.matches = []
    mod_tp._tokens_search.match_set = set()
    mod_tp._tokens_search.current_idx = 0
    mod_search_bar.clear_selection(mod_tp._tokens_search)


def _capture_clipboard():
    captured = []
    orig = mod_tp.copy_to_clipboard
    mod_tp.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig


# TESTS

def test_state_shape_and_label():
    print("\n[shape] Tokens pane search state is one search_bar.SearchState, lowercase label")
    check("_tokens_search is a search_bar.SearchState instance",
          isinstance(mod_tp._tokens_search, mod_search_bar.SearchState))
    check("label is 'search: ' (lowercase, visual consistency with the majority of panes)",
          mod_tp._TOKENS_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_tp._TOKENS_SEARCH_BAR_LINES == 1)


def test_search_bar_row1_renders_no_arrows():
    print("\n[render] Search bar renders at row 1, no click-arrows")
    _reset_state()
    mod_tp._cache_turns.append(_make_turn(0))
    output = mod_tp._build_tokens_output()
    first_line = output.splitlines()[0]
    check("row 1 shows the 'search: ' label", 'search:' in first_line)
    check("no [<-] click-arrow", '[←]' not in first_line and '[→]' not in first_line)
    check("row 1 is not a body line_map key", mod_tp.cache_line_map.get(1) is None)


def test_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    changed = mod_tp._handle_tokens_mouse(0, len(label) + 2, 1)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_tp._tokens_search.focused is True)
    check("press arms dragging", mod_tp._tokens_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_tp._tokens_search.sel_anchor == mod_tp._tokens_search.sel_end == 1)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_tp._TOKENS_SEARCH_BAR_LABEL
        mod_tp._handle_tokens_mouse(0, len(label) + 2, 1)
        motion_changed = mod_tp._handle_tokens_mouse(32, len(label) + 7, 1)
        check("motion extends sel_end only", motion_changed and mod_tp._tokens_search.sel_end == 6)
        release_changed = mod_tp._handle_tokens_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_tp._tokens_search.dragging is False)
        check("release copies exactly the selected substring", captured == ['ello '])
    finally:
        mod_tp.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion makes zero clipboard calls")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_tp._TOKENS_SEARCH_BAR_LABEL
        mod_tp._handle_tokens_mouse(0, len(label) + 3, 1)
        release_changed = mod_tp._handle_tokens_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
        check("selection cleared after a plain click",
              mod_tp._tokens_search.sel_anchor is None and mod_tp._tokens_search.sel_end is None)
    finally:
        mod_tp.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    changed = mod_tp._handle_tokens_search_release()
    check("release with no armed drag returns False", changed is False)


def test_body_click_clears_selection():
    print("\n[clear] Click on the body (row >= 2, unmapped) clears a live drag-selection")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    mod_tp._handle_tokens_mouse(0, len(label) + 1, 1)
    mod_tp._handle_tokens_mouse(32, len(label) + 5, 1)
    mod_tp._handle_tokens_search_release()
    check("selection exists before the elsewhere-click", mod_tp._tokens_search.sel_anchor is not None)
    changed = mod_tp._handle_tokens_mouse(0, 5, 10)  # unmapped body row
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_tp._tokens_search.sel_anchor is None and mod_tp._tokens_search.sel_end is None)


def test_body_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    mod_tp._handle_tokens_mouse(0, 5, 10)
    check("body-row press does not arm dragging", mod_tp._tokens_search.dragging is False)
    mod_tp._handle_tokens_mouse(32, 40, 10)
    check("motion after a body-row press falls through to generic hover", mod_tp.cache_hover_row == 10)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    mod_tp._handle_tokens_mouse(0, len(label) + 1, 1)
    mod_tp._handle_tokens_mouse(32, len(label) + 5, 1)
    mod_tp._handle_tokens_search_release()
    check("selection exists before typing", mod_tp._tokens_search.sel_anchor is not None)
    changed = mod_tp._handle_tokens_search_input('x')
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_tp._tokens_search.sel_anchor is None and mod_tp._tokens_search.sel_end is None)
    check("typed char appended at the end", mod_tp._tokens_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED substring")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    mod_tp._handle_tokens_mouse(0, len(label) + 2, 1)
    mod_tp._handle_tokens_mouse(32, len(label) + 7, 1)
    mod_tp._handle_tokens_search_release()
    changed = mod_tp._handle_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed", mod_tp._tokens_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_tp._tokens_search.sel_anchor is None and mod_tp._tokens_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with no selection still trims the last char")
    _reset_state('hello')
    changed = mod_tp._handle_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("last char trimmed", mod_tp._tokens_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query")
    _reset_state('some fairly long search query text')
    changed = mod_tp._handle_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_tp._tokens_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (plain backspace, kill-line) never clears _tokens_search.matches "
          "— Enter remains the sole recompute trigger")
    _reset_state('foo')
    mod_tp._tokens_search.matches = [(0, 0), (1, 0)]
    mod_tp._tokens_search.match_set = {(0, 0), (1, 0)}
    mod_tp._handle_tokens_search_input('\x7f')
    check("matches survive plain backspace", mod_tp._tokens_search.matches == [(0, 0), (1, 0)])
    mod_tp._handle_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("matches survive kill-line", mod_tp._tokens_search.matches == [(0, 0), (1, 0)])


def test_call_level_match_collapsed_container_marked():
    print("\n[match: call, collapsed] Whole call-header line container-marked even though the "
          "match text lives in unrendered (collapsed) detail content")
    _reset_state('unique_marker_x')
    mod_tp._cache_turns.append(_make_turn(0, call_marker='unique_marker_x'))
    check("call is NOT expanded", mod_tp.cache_expand_states.get((0, 0), False) is False)
    changed = mod_tp._handle_tokens_search_input('\r')
    check("Enter reports a change", changed)
    check("real search found the call (force-expand matcher sees collapsed content)",
          mod_tp._tokens_search.matches == [(0, 0)])
    output = mod_tp._build_tokens_output()
    row = next(r for r, k in mod_tp.cache_line_map.items() if k == (0, 0))
    header_line = output.splitlines()[row - 1]
    check("collapsed call header line is container-marked (SEARCH_CURRENT_BG present)",
          mod_colors.SEARCH_CURRENT_BG in header_line)
    check("the marker text itself does NOT leak into the collapsed row (still collapsed)",
          'unique_marker_x' not in header_line)


def test_call_level_match_expanded_substring_marked():
    print("\n[match: call, expanded] Header stays container-marked AND the specific matching "
          "detail line gets browser-find substring-highlighted")
    _reset_state('unique_marker_x')
    mod_tp._cache_turns.append(_make_turn(0, call_marker='unique_marker_x'))
    mod_tp.cache_expand_states[(0, 0)] = True
    mod_tp._handle_tokens_search_input('\r')
    check("real search found the call", mod_tp._tokens_search.matches == [(0, 0)])
    output = mod_tp._build_tokens_output()
    header_row = next(r for r, k in mod_tp.cache_line_map.items() if k == (0, 0))
    header_line = output.splitlines()[header_row - 1]
    check("header line STILL container-marked when expanded (uniform, orientation-preserving)",
          mod_colors.SEARCH_CURRENT_BG in header_line)
    check("the matched substring itself is browser-find highlighted somewhere in the output",
          f"{mod_colors.SEARCH_CURRENT_BG}unique_marker_x\033[49m" in output)
    check("no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output",
          mod_search_bar._BG_RESTORE_SENTINEL not in output)


def test_turn_level_match():
    print("\n[match: turn] A match in the turn's own prompt line gets the turn header container-marked")
    _reset_state('unique_turn_marker')
    mod_tp._cache_turns.append(_make_turn(0, prompt_marker='unique_turn_marker'))
    changed = mod_tp._handle_tokens_search_input('\r')
    check("Enter reports a change", changed)
    check("real search found the turn", mod_tp._tokens_search.matches == [('turn', 0)])
    output = mod_tp._build_tokens_output()
    check("turn header is container-marked in the rendered output",
          mod_colors.SEARCH_CURRENT_BG in output and 'unique_turn_marker' in output)
    check("no ('turn', 0) key leaked into cache_line_map (turn headers stay non-interactive)",
          ('turn', 0) not in mod_tp.cache_line_map.values())


def test_n_N_jump_wraps_both_directions():
    print("\n[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches")
    _reset_state()
    check("no-op with zero matches", mod_tp._jump_tokens_search_match(forward=True) is False)
    mod_tp._tokens_search.matches = [(0, 0), ('turn', 1), (2, 0)]
    mod_tp._tokens_search.current_idx = 0
    check("n advances to idx 1", mod_tp._jump_tokens_search_match(forward=True) and mod_tp._tokens_search.current_idx == 1)
    check("n advances to idx 2", mod_tp._jump_tokens_search_match(forward=True) and mod_tp._tokens_search.current_idx == 2)
    check("n wraps back to idx 0", mod_tp._jump_tokens_search_match(forward=True) and mod_tp._tokens_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_tp._jump_tokens_search_match(forward=False) and mod_tp._tokens_search.current_idx == 2)


def test_esc_cancel_clears_state_bar_stays():
    print("\n[Esc] Cancel clears query/matches/selection; the bar itself is never hidden")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    mod_tp._tokens_search.focused = True
    mod_tp._tokens_search.matches = [(0, 0)]
    mod_tp._tokens_search.match_set = {(0, 0)}
    mod_tp._handle_tokens_mouse(0, len(label) + 1, 1)
    mod_tp._handle_tokens_mouse(32, len(label) + 5, 1)
    mod_tp._handle_tokens_search_release()
    changed = mod_tp._handle_tokens_search_cancel()
    check("cancel reports a change", changed)
    check("query cleared", mod_tp._tokens_search.query == '')
    check("matches cleared", mod_tp._tokens_search.matches == [] and mod_tp._tokens_search.match_set == set())
    check("focused cleared", mod_tp._tokens_search.focused is False)
    check("selection cleared", mod_tp._tokens_search.sel_anchor is None)
    bar = mod_tp._render_tokens_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring")
    _reset_state('hello world')
    label = mod_tp._TOKENS_SEARCH_BAR_LABEL
    mod_tp._handle_tokens_mouse(0, len(label) + 2, 1)
    mod_tp._handle_tokens_mouse(32, len(label) + 7, 1)
    mod_tp._handle_tokens_search_release()
    bar = mod_tp._render_tokens_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring", '\033[7mello \033[27m' in bar)

    _reset_state('hello world')
    bar2 = mod_tp._render_tokens_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)


def test_sentinel_resolves_to_default_bg_not_empty_string():
    print("\n[sentinel fix] Same bug class as the proxy pane: ZEBRA_BG_A=='' — the sentinel "
          "must resolve to an explicit \\033[49m on a detail line, not be deleted outright "
          "(which would flood the search highlight color to the rest of the row)")
    check("ZEBRA_BG_A is indeed the empty string (confirms the trap applies here)",
          mod_colors.ZEBRA_BG_A == '')
    _reset_state('unique_marker_z')
    mod_tp._cache_turns.append(_make_turn(0, call_marker='unique_marker_z'))
    mod_tp.cache_expand_states[(0, 0)] = True
    mod_tp._handle_tokens_search_input('\r')
    output = mod_tp._build_tokens_output()
    check("an explicit \\033[49m appears right after the highlighted detail-line text",
          f"unique_marker_z\033[49m" in output)
    check("no raw _BG_RESTORE_SENTINEL leaked into the final output",
          mod_search_bar._BG_RESTORE_SENTINEL not in output)


def test_light_red_bg_still_detected_when_call_is_also_a_match():
    print("\n[regression] LIGHT_RED_BG (cc_broken row) detection uses 'in line', not "
          "'.startswith()' — a search-match wrap now precedes it in the string")
    _reset_state('unique_marker_w')
    # cache_creation > cache_read triggers cc_broken -> LIGHT_RED_BG prefix in _format_cache_call
    mod_tp._cache_turns.append(_make_turn(0, call_marker='unique_marker_w', cache_read=100, cache_creation=500))
    mod_tp._handle_tokens_search_input('\r')
    check("real search found the (also cc_broken) call", mod_tp._tokens_search.matches == [(0, 0)])
    output = mod_tp._build_tokens_output()
    row = next(r for r, k in mod_tp.cache_line_map.items() if k == (0, 0))
    header_line = output.splitlines()[row - 1]
    check("row's OUTER chosen_bg is still LIGHT_RED_BG despite the search-marker wrap preceding it",
          header_line.startswith(mod_colors.LIGHT_RED_BG))


def test_jump_to_match_moves_scroll_offset():
    print("\n[jump] Enter jumps cache_scroll_offset to bring an off-screen early match into view")
    _reset_state('unique_marker_early')
    for i in range(40):
        mod_tp._cache_turns.append(_make_turn(i, call_marker='unique_marker_early' if i == 0 else None))
    # _tokens_nav is populated by the LAST render (mirrors core/monitor_display.py's
    # ensure_match_visible reading _search_all_line_offsets) — one render must happen first,
    # exactly as it would in the live pane loop (the pane is always rendering independently of
    # search actions).
    mod_tp._build_tokens_output()
    check("scroll starts at 0 (default view = newest/bottom)", mod_tp.cache_scroll_offset == 0)
    mod_tp._handle_tokens_search_input('\r')
    check("real search found the early call", mod_tp._tokens_search.matches == [(0, 0)])
    check("jump pushed cache_scroll_offset above 0 (turn 0 is far from the default bottom view)",
          mod_tp.cache_scroll_offset > 0)


def test_session_change_resets_search_state():
    print("\n[worker switch parity] Session change resets _tokens_search and _tokens_nav — "
          "mirrors pane.py's session-change reset and the fix applied to the main pane and "
          "the worker-proxy pane")
    _reset_state('hello world')
    mod_tp._cache_turns.append(_make_turn(0, call_marker='hello world'))
    mod_tp._tokens_search.matches = [(0, 0)]
    mod_tp._tokens_search.match_set = {(0, 0)}
    mod_tp._tokens_search.focused = True
    mod_tp._tokens_nav[(0, 0)] = 3
    mod_tp._cache_current_filepath = Path('/tmp/pane_search_p6_fake_session_old.jsonl')
    check("search state populated before the session change",
          mod_tp._tokens_search.matches == [(0, 0)] and mod_tp._tokens_search.query == 'hello world')

    fake_new_session = Path('/tmp/pane_search_p6_fake_session_new.jsonl')
    orig_get_sessions = mod_monitor.get_main_session_files
    orig_find_resp = mod_parser.find_response_log_path
    orig_read_resp = mod_side_logs.read_response_log
    mod_monitor.get_main_session_files = lambda: [fake_new_session]
    mod_parser.find_response_log_path = lambda pf: None
    mod_side_logs.read_response_log = lambda path, pos: ({}, pos)
    try:
        mod_tp._refresh_tokens_data(10_000_000.0, False, 0.0, 10_000_000.0)
    finally:
        mod_monitor.get_main_session_files = orig_get_sessions
        mod_parser.find_response_log_path = orig_find_resp
        mod_side_logs.read_response_log = orig_read_resp

    check("session actually changed", mod_tp._cache_current_filepath == fake_new_session)
    check("query cleared by the session change", mod_tp._tokens_search.query == '')
    check("matches cleared by the session change",
          mod_tp._tokens_search.matches == [] and mod_tp._tokens_search.match_set == set())
    check("focused cleared by the session change", mod_tp._tokens_search.focused is False)
    check("_tokens_nav cleared by the session change", mod_tp._tokens_nav == {})


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P6 — tokens pane search bar parity regression suite")
    print("=" * 70)
    test_state_shape_and_label()
    test_search_bar_row1_renders_no_arrows()
    test_row1_press_focuses_and_arms_drag()
    test_drag_select_copies_to_clipboard()
    test_plain_click_no_motion_no_clipboard()
    test_release_noop_without_active_drag()
    test_body_click_clears_selection()
    test_body_drag_never_arms_search_selection()
    test_new_input_clears_selection()
    test_backspace_deletes_active_selection()
    test_backspace_without_selection_still_trims_last_char()
    test_kill_line_empties_query()
    test_editing_never_clears_matches()
    test_call_level_match_collapsed_container_marked()
    test_call_level_match_expanded_substring_marked()
    test_turn_level_match()
    test_n_N_jump_wraps_both_directions()
    test_esc_cancel_clears_state_bar_stays()
    test_render_reverse_video_bracket()
    test_sentinel_resolves_to_default_bg_not_empty_string()
    test_light_red_bg_still_detected_when_call_is_also_a_match()
    test_jump_to_match_moves_scroll_offset()
    test_session_change_resets_search_state()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p6_tokens_pane_parity_test_{ts}.md'
    lines = [f"# P6 tokens pane parity regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
