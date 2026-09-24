# INFRASTRUCTURE
import shutil
import tempfile
from pathlib import Path

from p7_workers_pane_parity_fixtures import (
    mod_wt, mod_colors, mod_search_bar, _MONITOR, check, _reset_state,
    _setup_one_worker_jsonl, _cleanup_worker_jsonl, _load_turns_via_refresh, _select_worker,
)

# FUNCTIONS

def test_call_level_match_collapsed_container_marked():
    print("\n[match: call, collapsed] Whole call-header line container-marked even though the "
          "match text lives in unrendered (collapsed) detail content -- real worker JSONL fixture")
    _reset_state('unique_marker_x')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'do the build', call_marker='unique_marker_x')
    try:
        _load_turns_via_refresh(worker)
        check("call is NOT expanded", mod_wt.worker_tokens_expand_states.get((0, 0), False) is False)
        changed = mod_wt._handle_worker_tokens_search_input('\r')
        check("Enter reports a change", changed)
        check("real search found the call", mod_wt._worker_tokens_search.matches == [(0, 0)])
        output = mod_wt._build_worker_tokens_output(_MONITOR)
        row = next(r for r, k in mod_wt.worker_tokens_line_map.items() if k == (0, 0))
        header_line = output.splitlines()[row - 1]
        check("collapsed call header line is container-marked (SEARCH_CURRENT_BG present)",
              mod_colors.SEARCH_CURRENT_BG in header_line)
        check("the marker text itself does NOT leak into the collapsed row (still collapsed)",
              'unique_marker_x' not in header_line)
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_call_level_match_expanded_substring_marked():
    print("\n[match: call, expanded] Header stays container-marked AND the specific matching "
          "detail line gets browser-find substring-highlighted")
    _reset_state('unique_marker_x')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'do the build', call_marker='unique_marker_x')
    try:
        _load_turns_via_refresh(worker)
        mod_wt.worker_tokens_expand_states[(0, 0)] = True
        mod_wt._handle_worker_tokens_search_input('\r')
        check("real search found the call", mod_wt._worker_tokens_search.matches == [(0, 0)])
        output = mod_wt._build_worker_tokens_output(_MONITOR)
        header_row = next(r for r, k in mod_wt.worker_tokens_line_map.items() if k == (0, 0))
        header_line = output.splitlines()[header_row - 1]
        check("header line STILL container-marked when expanded", mod_colors.SEARCH_CURRENT_BG in header_line)
        check("the matched substring itself is browser-find highlighted somewhere in the output",
              f"{mod_colors.SEARCH_CURRENT_BG}unique_marker_x\033[49m" in output)
        check("no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output",
              mod_search_bar._BG_RESTORE_SENTINEL not in output)
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_turn_level_match():
    print("\n[match: turn] A match in the turn's own prompt line gets the turn header container-marked")
    _reset_state('unique_turn_marker')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'do the build unique_turn_marker')
    try:
        _load_turns_via_refresh(worker)
        changed = mod_wt._handle_worker_tokens_search_input('\r')
        check("Enter reports a change", changed)
        check("real search found the turn", mod_wt._worker_tokens_search.matches == [('turn', 0)])
        output = mod_wt._build_worker_tokens_output(_MONITOR)
        check("turn header is container-marked in the rendered output",
              mod_colors.SEARCH_CURRENT_BG in output and 'unique_turn_marker' in output)
        check("no ('turn', 0) key leaked into worker_tokens_line_map (turn headers stay non-interactive)",
              ('turn', 0) not in mod_wt.worker_tokens_line_map.values())
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_light_red_bg_still_detected_when_call_is_also_a_match():
    print("\n[regression] LIGHT_RED_BG (cc_broken row) detection uses 'in line', not "
          "'.startswith()' -- a search-match wrap now precedes it in the string")
    _reset_state('unique_marker_w')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'prompt', call_marker='unique_marker_w')
    try:
        _load_turns_via_refresh(worker)
        mod_wt._handle_worker_tokens_search_input('\r')
        check("real search found the call", mod_wt._worker_tokens_search.matches == [(0, 0)])
        mod_wt._worker_tokens_turns[0]['api_calls'][0]['cache_creation'] = 5000
        mod_wt._worker_tokens_turns[0]['api_calls'][0]['cache_read'] = 100
        output = mod_wt._build_worker_tokens_output(_MONITOR)
        row = next(r for r, k in mod_wt.worker_tokens_line_map.items() if k == (0, 0))
        header_line = output.splitlines()[row - 1]
        check("row's OUTER chosen_bg is still LIGHT_RED_BG despite the search-marker wrap preceding it",
              header_line.startswith(mod_colors.LIGHT_RED_BG))
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_n_N_jump_wraps_both_directions():
    print("\n[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches")
    _reset_state()
    check("no-op with zero matches", mod_wt._jump_worker_tokens_search_match(forward=True) is False)
    mod_wt._worker_tokens_search.matches = [(0, 0), ('turn', 1), (2, 0)]
    mod_wt._worker_tokens_search.current_idx = 0
    check("n advances to idx 1", mod_wt._jump_worker_tokens_search_match(forward=True) and mod_wt._worker_tokens_search.current_idx == 1)
    check("n advances to idx 2", mod_wt._jump_worker_tokens_search_match(forward=True) and mod_wt._worker_tokens_search.current_idx == 2)
    check("n wraps back to idx 0", mod_wt._jump_worker_tokens_search_match(forward=True) and mod_wt._worker_tokens_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_wt._jump_worker_tokens_search_match(forward=False) and mod_wt._worker_tokens_search.current_idx == 2)


def test_sentinel_resolves_to_default_bg_not_empty_string():
    print("\n[sentinel fix] Same bug class as the proxy/tokens/worker-proxy panes: ZEBRA_BG_A=='' "
          "-- the sentinel must resolve to an explicit \\033[49m on a detail line, not be deleted "
          "outright (which would flood the search highlight color to the rest of the row)")
    check("ZEBRA_BG_A is indeed the empty string (confirms the trap applies here)",
          mod_colors.ZEBRA_BG_A == '')
    _reset_state('unique_marker_z')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'prompt', call_marker='unique_marker_z')
    try:
        _load_turns_via_refresh(worker)
        mod_wt.worker_tokens_expand_states[(0, 0)] = True
        mod_wt._handle_worker_tokens_search_input('\r')
        output = mod_wt._build_worker_tokens_output(_MONITOR)
        check("an explicit \\033[49m appears right after the highlighted detail-line text",
              f"unique_marker_z\033[49m" in output)
        check("no raw _BG_RESTORE_SENTINEL leaked into the final output",
              mod_search_bar._BG_RESTORE_SENTINEL not in output)
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_jump_to_match_moves_scroll_offset():
    print("\n[jump] Enter jumps worker_tokens_scroll_offset to bring an off-screen early match into view")
    _reset_state('unique_marker_early')
    worker, orig_find = _setup_one_worker_jsonl('w1', 'prompt')
    try:
        _select_worker('w1', [worker])
        mod_wt._worker_tokens_turns = [
            {'timestamp': f'2026-01-01T00:{i:02d}:00Z', 'prompt': f'turn {i}',
             'api_calls': [{'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 10,
                            'content_blocks': [{'type': 'text', 'preview': 'unique_marker_early', 'chars': 20}] if i == 0 else []}]}
            for i in range(40)
        ]
        mod_wt._build_worker_tokens_output(_MONITOR)
        check("scroll starts at 0 (default view = newest/bottom)", mod_wt.worker_tokens_scroll_offset == 0)
        mod_wt._handle_worker_tokens_search_input('\r')
        check("real search found the early call", mod_wt._worker_tokens_search.matches == [(0, 0)])
        check("jump pushed worker_tokens_scroll_offset above 0 (turn 0 is far from the default bottom view)",
              mod_wt.worker_tokens_scroll_offset > 0)
    finally:
        _cleanup_worker_jsonl(orig_find)


def test_worker_switch_resets_search_state_and_scroll():
    print("\n[worker switch] Switching the selected worker resets _worker_tokens_search AND "
          "worker_tokens_scroll_offset -- a DELIBERATE behavior change from the deleted "
          "worker_pane.py, which had no current-worker concept to switch away from; mirrors "
          "worker_proxy_pane.py's own worker-switch reset")
    _reset_state('hello world')
    mod_wt._worker_tokens_turns = [{
        'prompt': 'hello world', 'timestamp': '2026-01-01T00:00:00Z',
        'api_calls': [{'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 10, 'content_blocks': []}],
    }]
    mod_wt._worker_tokens_search.matches = [('turn', 0)]
    mod_wt._worker_tokens_search.match_set = {('turn', 0)}
    mod_wt._worker_tokens_search.focused = True
    mod_wt.worker_tokens_scroll_offset = 7
    mod_wt._worker_tokens_current_name = 'workerA'
    check("search state populated before the switch",
          mod_wt._worker_tokens_search.matches == [('turn', 0)] and mod_wt._worker_tokens_search.query == 'hello world')

    tmp_dir = Path(tempfile.mkdtemp(prefix='pane_search_p7_switch_'))
    sel_path = tmp_dir / 'selection.txt'
    sel_path.write_text('workerB', encoding='utf-8')
    orig_get_sel = mod_wt.get_selection_file_path
    orig_list_workers = mod_wt.list_workers
    mod_wt.get_selection_file_path = lambda pf: sel_path
    mod_wt.list_workers = lambda pf: [{'name': 'workerB', 'session': ''}]
    try:
        mod_wt._refresh_worker_tokens_data(10_000_000.0, False, 0.0, _MONITOR)
    finally:
        mod_wt.get_selection_file_path = orig_get_sel
        mod_wt.list_workers = orig_list_workers
        shutil.rmtree(tmp_dir, ignore_errors=True)

    check("selected worker actually changed", mod_wt._worker_tokens_current_name == 'workerB')
    check("query cleared by the worker switch", mod_wt._worker_tokens_search.query == '')
    check("matches cleared by the worker switch",
          mod_wt._worker_tokens_search.matches == [] and mod_wt._worker_tokens_search.match_set == set())
    check("focused cleared by the worker switch", mod_wt._worker_tokens_search.focused is False)
    check("scroll offset reset to 0 by the worker switch", mod_wt.worker_tokens_scroll_offset == 0)
    check("turns cleared by the worker switch (stale worker's data does not leak)",
          mod_wt._worker_tokens_turns == [])
