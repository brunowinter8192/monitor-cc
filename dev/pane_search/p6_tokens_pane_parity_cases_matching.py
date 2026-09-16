# INFRASTRUCTURE
from pathlib import Path

from p6_tokens_pane_parity_fixtures import (
    mod_tp, mod_search_bar, mod_colors, mod_monitor, mod_parser, mod_side_logs,
    check, _make_turn, _reset_state,
)

# FUNCTIONS

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
