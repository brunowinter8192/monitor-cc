# INFRASTRUCTURE
import shutil
import tempfile
from pathlib import Path

from p5_worker_proxy_pane_parity_fixtures import (
    mod_wp, mod_search_bar, _FakeMonitor, PANE_WIDTH, check, _make_wp_entry, _reset_state, _click, _fwd_line,
)

# FUNCTIONS

def test_enter_runs_real_search_no_log_path():
    print("\n[real search] Enter with _worker_proxy_log_path=None skips reconstruction and runs "
          "build_search_matches directly against the pre-populated synthetic entries")
    _reset_state('unique_marker_1')
    mod_wp.worker_proxy_entries.extend(_make_wp_entry(i) for i in range(3))
    check("_worker_proxy_log_path is None (no reconstruction)", mod_wp._worker_proxy_log_path is None)
    changed = mod_wp._handle_worker_proxy_search_input('\r')
    check("Enter reports a change", changed)
    check("real search found exactly entry 1", mod_wp._worker_proxy_search.matches == [1])
    check("match_set mirrors matches", mod_wp._worker_proxy_search.match_set == {1})
    check("current_idx reset to 0", mod_wp._worker_proxy_search.current_idx == 0)
    check("Enter unfocuses the bar", mod_wp._worker_proxy_search.focused is False)
    check("_wp_just_expanded set to the match's req key (reuses the expand-click auto-scroll anchor)",
          mod_wp._wp_just_expanded == ('req', 1))


def test_enter_always_reruns_not_gated_on_unchanged_query():
    print("\n[always-rerun] A repeated Enter with the SAME query re-runs the search — no "
          "unchanged-query gate exists on this pane (proxy's convention, nothing to correct here)")
    _reset_state('marker_b')
    mod_wp.worker_proxy_entries.append(_make_wp_entry(0, 'marker_b'))
    mod_wp._handle_worker_proxy_search_input('\r')
    check("first Enter found 1 match", mod_wp._worker_proxy_search.matches == [0])
    mod_wp._worker_proxy_search.focused = True
    mod_wp.worker_proxy_entries.append(_make_wp_entry(1, 'marker_b'))
    mod_wp._handle_worker_proxy_search_input('\r')
    check("second Enter (same query) picked up the new entry -> 2 matches now",
          mod_wp._worker_proxy_search.matches == [0, 1])


def test_enter_triggers_reconstruction_merge_when_log_path_set():
    print("\n[reconstruction] Enter merges reconstruct_all_messages(fwd_path) by flow_id into "
          "worker_proxy_entries when _worker_proxy_log_path is set — the NEW wiring for this pane")
    tmp = Path(tempfile.mkdtemp(prefix='pane_search_p5_fwd_'))
    dual_log_dir = tmp / 'dual_log'
    dual_log_dir.mkdir()
    log_path = tmp / 'api_requests_worker_abc12345_alpha_1.jsonl'
    fwd_path = dual_log_dir / 'api_requests_worker_abc12345_alpha_1_forwarded.jsonl'
    lines = [
        _fwd_line('flow-0', 'claude-opus-5', True, 'plain filler'),
        _fwd_line('flow-1', 'claude-opus-5', False, 'reconstructed_marker_text'),
    ]
    fwd_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    try:
        _reset_state('reconstructed_marker_text')
        mod_wp.worker_proxy_entries.extend([
            {**_make_wp_entry(0), 'flow_id': 'flow-0', 'messages': None},
            {**_make_wp_entry(1), 'flow_id': 'flow-1', 'messages': None},
        ])
        mod_wp._worker_proxy_log_path = log_path
        changed = mod_wp._handle_worker_proxy_search_input('\r')
        check("Enter reports a change", changed)
        check("entry 1's messages were populated from the reconstruction merge (were None before)",
              mod_wp.worker_proxy_entries[1]['messages'] is not None)
        check("the reconstructed content is findable — real search found entry 1",
              mod_wp._worker_proxy_search.matches == [1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_n_N_jump_wraps_both_directions():
    print("\n[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches")
    _reset_state()
    check("no-op with zero matches", mod_wp._jump_worker_search_match(forward=True) is False)
    mod_wp._worker_proxy_search.matches = [5, 12, 30]
    mod_wp._worker_proxy_search.current_idx = 0
    check("n advances to idx 1", mod_wp._jump_worker_search_match(forward=True) and mod_wp._worker_proxy_search.current_idx == 1)
    check("n advances to idx 2", mod_wp._jump_worker_search_match(forward=True) and mod_wp._worker_proxy_search.current_idx == 2)
    check("n wraps back to idx 0", mod_wp._jump_worker_search_match(forward=True) and mod_wp._worker_proxy_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_wp._jump_worker_search_match(forward=False) and mod_wp._worker_proxy_search.current_idx == 2)
    check("_wp_just_expanded tracks the current match's req key", mod_wp._wp_just_expanded == ('req', 30))


def test_esc_cancel_clears_state_bar_stays():
    print("\n[Esc] Cancel clears query/matches/selection; the bar itself is never hidden")
    _reset_state('hello world')
    label = mod_wp._WP_SEARCH_BAR_LABEL
    mod_wp._worker_proxy_search.focused = True
    mod_wp._worker_proxy_search.matches = [1, 2]
    mod_wp._worker_proxy_search.match_set = {1, 2}
    _click(0, len(label) + 1, 1)
    _click(32, len(label) + 5, 1)
    mod_wp._handle_worker_proxy_search_release()
    changed = mod_wp._handle_worker_proxy_search_cancel()
    check("cancel reports a change", changed)
    check("query cleared", mod_wp._worker_proxy_search.query == '')
    check("matches cleared", mod_wp._worker_proxy_search.matches == [] and mod_wp._worker_proxy_search.match_set == set())
    check("focused cleared", mod_wp._worker_proxy_search.focused is False)
    check("selection cleared", mod_wp._worker_proxy_search.sel_anchor is None)
    bar = mod_wp._render_worker_proxy_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)


def test_worker_switch_resets_search_state():
    print("\n[worker switch] Switching the selected worker resets _worker_proxy_search — mirrors "
          "pane.py's session-change reset and the fix just landed on the main pane; fires for "
          "BOTH digit-key and header-marker selection (both converge on this same code path)")
    _reset_state('hello world')
    mod_wp.worker_proxy_entries.append(_make_wp_entry(0, 'hello world'))
    mod_wp._worker_proxy_search.matches = [0]
    mod_wp._worker_proxy_search.match_set = {0}
    mod_wp._worker_proxy_search.focused = True
    mod_wp._worker_proxy_last_worker_name = 'workerA'  # pretend we're currently on workerA
    check("search state populated before the switch",
          mod_wp._worker_proxy_search.matches == [0] and mod_wp._worker_proxy_search.query == 'hello world')

    tmp_dir = Path(tempfile.mkdtemp(prefix='pane_search_p5_switch_'))
    sel_path = tmp_dir / 'selection.txt'
    sel_path.write_text('workerB', encoding='utf-8')
    orig_get_sel = mod_wp.get_selection_file_path
    orig_list_workers = mod_wp.list_workers
    orig_find_log = mod_wp.find_worker_proxy_log
    mod_wp.get_selection_file_path = lambda pf: sel_path
    mod_wp.list_workers = lambda pf: [{'name': 'workerB', 'session': ''}]
    mod_wp.find_worker_proxy_log = lambda name, pf=None: None
    try:
        mod_wp._refresh_worker_proxy_data(10_000_000.0, False, 0.0, _FakeMonitor())
    finally:
        mod_wp.get_selection_file_path = orig_get_sel
        mod_wp.list_workers = orig_list_workers
        mod_wp.find_worker_proxy_log = orig_find_log
        shutil.rmtree(tmp_dir, ignore_errors=True)

    check("selected worker actually changed", mod_wp._worker_proxy_last_worker_name == 'workerB')
    check("query cleared by the worker switch", mod_wp._worker_proxy_search.query == '')
    check("matches cleared by the worker switch",
          mod_wp._worker_proxy_search.matches == [] and mod_wp._worker_proxy_search.match_set == set())
    check("focused cleared by the worker switch", mod_wp._worker_proxy_search.focused is False)
