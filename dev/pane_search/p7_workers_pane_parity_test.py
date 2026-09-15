"""
p7_workers_pane_parity_test.py -- Regression guard for the worker-tokens pane's search bar and
worker-switch header (rollout sub-milestone 5 originally targeted the all-workers list pane,
worker_pane.py; RETARGETED 2026-09 for the panesplit milestone, since that pane is gone -- the
workers list was replaced with worker_tokens_pane.py, a single-selected-worker cache tracker
carrying a switch header, mirroring worker_proxy_pane.py's own shape).

worker_tokens_pane.py is now structurally the tokens pane's closest twin (single cache-tracker
view, `format_cache_tracker`, two-tier match keys) PLUS the worker-proxy pane's own switch-header
mechanics (2-row header: search bar row 1, worker-switch markers row 2+, IPC-file-driven
worker-switch reset). This suite covers both halves:

  - THE SAME MECHANICS SUITE AS p6_tokens_pane_parity_test.py: drag-select press/motion/release,
    editor-style deletion (selection-delete Backspace, kill-line), n/N jump, Esc, the
    `ZEBRA_BG_A == ''` sentinel-resolution bug (now a 4th occurrence, same fix each time), the
    `LIGHT_RED_BG` detection regression (`.startswith()` -> `in`) -- because only ONE worker is
    ever visible at a time now, match keys are the plain `(turn_idx, call_idx)` / `('turn',
    turn_idx)` two-tier shape `token_pane.py` already uses -- NOT the old three-tier
    worker-wrapped shape (`(name, turn_idx, call_idx)`) the deleted worker_pane.py needed, since
    there is no second, simultaneously-visible worker's content left to accidentally leak into.
  - THE 2-ROW HEADER + WORKER-SWITCH MECHANICS OF p5_worker_proxy_pane_parity_test.py: search bar
    row 1, worker-switch header row 2+ (built by the SAME shared
    `workers/worker_switch_header.py::format_worker_switch_header` the worker-proxy pane uses),
    and a NEW worker-switch reset. This is a deliberate behavior CHANGE from the deleted
    worker_pane.py, which explicitly had NO worker-switch reset (documented there as "no single
    current worker to switch away from" -- true for a list showing every worker at once, false
    for this pane, which now has exactly one current worker, same as worker-proxy). Switching
    worker resets search AND scroll to 0 -- the real successor to the old, vacuous
    `test_workers_scroll_reset_on_expand` in dev/display/test_hover_map.py (which never called
    real code to begin with).

Uses REAL src.workers.worker_tokens_pane / src.format.token_format / src.panes.token_search
functions against synthetic turns, plus real throwaway JSONL fixture files (find_worker_jsonl
monkeypatched to point at them) for the match-search tests -- not mocks of the reconstruction
pipeline itself. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p7_workers_pane_parity_test.py
"""

# INFRASTRUCTURE
import importlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_wt = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')

PANE_WIDTH = 100
_PROJECT_FILTER = '/tmp/p7proj'
_MONITOR = SimpleNamespace(active_project_filter=_PROJECT_FILTER)
_RESULTS = []
_TMP_ROOT = None


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

def _reset_state(query: str = ''):
    mod_wt.worker_tokens_expand_states.clear()
    mod_wt.worker_tokens_line_map.clear()
    mod_wt.worker_tokens_hover_row = None
    mod_wt.worker_tokens_scroll_offset = 0
    mod_wt.worker_tokens_copy_rows.clear()
    mod_wt._worker_tokens_copy_feedback_until.clear()
    mod_wt._worker_tokens_pane_width = PANE_WIDTH
    mod_wt._worker_tokens_turns = []
    mod_wt._worker_tokens_workers = []
    mod_wt._worker_tokens_current_name = None
    mod_wt._worker_tokens_force_reload = False
    mod_wt._worker_tokens_header_regions.clear()
    mod_wt._worker_tokens_header_lines = 2
    mod_wt._worker_tokens_nav.clear()
    mod_wt._worker_tokens_search.query = query
    mod_wt._worker_tokens_search.focused = False
    mod_wt._worker_tokens_search.matches = []
    mod_wt._worker_tokens_search.match_set = set()
    mod_wt._worker_tokens_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wt._worker_tokens_search)
    sel_path = mod_wt.get_selection_file_path(_PROJECT_FILTER)
    if os.path.exists(sel_path):
        os.remove(sel_path)


def _select_worker(name: str, workers: list) -> None:
    mod_wt._worker_tokens_workers = workers
    mod_wt.write_selection(_PROJECT_FILTER, name)
    mod_wt._worker_tokens_current_name = name


# Write a real throwaway JSONL fixture (one user prompt + optional one assistant tool_use call)
# for a single worker, monkeypatch find_worker_jsonl to resolve it. Real reconstruction pipeline
# (read_new_lines -> parse_jsonl_lines -> extract_cache_turns, via panes.cache_turns.build_cache_turns)
# runs unmocked -- only the tmux-session -> path RESOLUTION is stubbed.
def _setup_one_worker_jsonl(name: str, prompt: str, call_marker: str = None):
    global _TMP_ROOT
    _TMP_ROOT = Path(tempfile.mkdtemp(prefix='pane_search_p7_'))
    session = f'sess-{name}'
    path = _TMP_ROOT / f'{name}.jsonl'
    lines = [json.dumps({
        'type': 'user', 'userType': 'external', 'message': {'content': prompt},
        'timestamp': '2026-01-01T00:00:00Z',
    })]
    if call_marker:
        content = [{'type': 'tool_use', 'name': 'Bash', 'input': {'command': call_marker}}]
        lines.append(json.dumps({
            'type': 'assistant',
            'message': {
                'usage': {'cache_read_input_tokens': 1000, 'cache_creation_input_tokens': 0,
                          'input_tokens': 0, 'output_tokens': 10},
                'content': content,
            },
            'timestamp': '2026-01-01T00:00:01Z',
        }))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    worker = {'name': name, 'status': 'working', 'session': session}
    orig_find = mod_wt.find_worker_jsonl
    mod_wt.find_worker_jsonl = lambda s, _p=path, _s=session: (_p if s == _s else None)
    return worker, orig_find


def _cleanup_worker_jsonl(orig_find):
    global _TMP_ROOT
    mod_wt.find_worker_jsonl = orig_find
    if _TMP_ROOT:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
        _TMP_ROOT = None


def _load_turns_via_refresh(worker: dict) -> None:
    _select_worker(worker['name'], [worker])
    jsonl_path = mod_wt.find_worker_jsonl(worker['session'])
    turns, pos = mod_wt.build_cache_turns(jsonl_path, 0, [])
    mod_wt._worker_tokens_turns = turns
    mod_wt._worker_tokens_jsonl_position = pos


def _capture_clipboard():
    captured = []
    orig = mod_wt.copy_to_clipboard
    mod_wt.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig


# TESTS

def test_state_shape_and_label():
    print("\n[shape] Worker-tokens search state is one search_bar.SearchState, lowercase label")
    check("_worker_tokens_search is a search_bar.SearchState instance",
          isinstance(mod_wt._worker_tokens_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_wt._WT_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_wt._WT_SEARCH_BAR_LINES == 1)


def test_two_row_header_composition():
    print("\n[2-row header] Search bar row 1, worker-switch header row 2+; body rows past both")
    _reset_state()
    worker = {'name': 'w1', 'status': 'working', 'context_pct': 40}
    _select_worker('w1', [worker])
    mod_wt._worker_tokens_turns = [{
        'prompt': 'do it', 'timestamp': '2026-01-01T00:00:00Z',
        'api_calls': [{'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 10, 'content_blocks': []}],
    }]
    output, header = mod_wt._build_worker_tokens_output(_MONITOR)
    lines = header.splitlines()
    check("row 1 (search bar) contains the label", 'search:' in lines[0])
    check("row 1 has no click-arrows", '[<-]' not in lines[0] and '[->]' not in lines[0])
    check("worker-switch header text appears on a LATER line, not row 1",
          any('WORKER-TOKENS' in l for l in lines[1:]))
    check("row 1 is not a body line_map key", mod_wt.worker_tokens_line_map.get(1) is None)
    check("row 2 (worker header) is not a body line_map key either",
          mod_wt.worker_tokens_line_map.get(2) is None)
    check("header regions exist and are all on rows >= 2 (shifted past the search bar)",
          bool(mod_wt._worker_tokens_header_regions) and
          all(er >= 2 for (_sc, _ec, er) in mod_wt._worker_tokens_header_regions))
    check("all body line_map rows are past both header rows",
          all(r >= 3 for r in mod_wt.worker_tokens_line_map))


def test_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    changed = mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_wt._worker_tokens_search.focused is True)
    check("press arms dragging", mod_wt._worker_tokens_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_wt._worker_tokens_search.sel_anchor == mod_wt._worker_tokens_search.sel_end == 1)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wt._WT_SEARCH_BAR_LABEL
        mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
        motion_changed = mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
        check("motion extends sel_end only", motion_changed and mod_wt._worker_tokens_search.sel_end == 6)
        release_changed = mod_wt._handle_worker_tokens_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_wt._worker_tokens_search.dragging is False)
        check("release copies exactly the selected substring", captured == ['ello '])
    finally:
        mod_wt.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion makes zero clipboard calls")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wt._WT_SEARCH_BAR_LABEL
        mod_wt._handle_worker_tokens_mouse(0, len(label) + 3, 1, _MONITOR)
        release_changed = mod_wt._handle_worker_tokens_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
        check("selection cleared after a plain click",
              mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)
    finally:
        mod_wt.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    changed = mod_wt._handle_worker_tokens_search_release()
    check("release with no armed drag returns False", changed is False)


def test_body_click_clears_selection():
    print("\n[clear] Click on the body (row >= 3, unmapped) clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    check("selection exists before the elsewhere-click", mod_wt._worker_tokens_search.sel_anchor is not None)
    changed = mod_wt._handle_worker_tokens_mouse(0, 5, 10, _MONITOR)  # unmapped body row
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)


def test_body_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    mod_wt._handle_worker_tokens_mouse(0, 5, 10, _MONITOR)
    check("body-row press does not arm dragging", mod_wt._worker_tokens_search.dragging is False)
    mod_wt._handle_worker_tokens_mouse(32, 40, 10, _MONITOR)
    check("motion after a body-row press falls through to generic hover", mod_wt.worker_tokens_hover_row == 10)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    check("selection exists before typing", mod_wt._worker_tokens_search.sel_anchor is not None)
    changed = mod_wt._handle_worker_tokens_search_input('x')
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)
    check("typed char appended at the end", mod_wt._worker_tokens_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED substring")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    changed = mod_wt._handle_worker_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed", mod_wt._worker_tokens_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_wt._worker_tokens_search.sel_anchor is None and mod_wt._worker_tokens_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with no selection still trims the last char")
    _reset_state('hello')
    changed = mod_wt._handle_worker_tokens_search_input('\x7f')
    check("backspace reports a change", changed)
    check("last char trimmed", mod_wt._worker_tokens_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query")
    _reset_state('some fairly long search query text')
    changed = mod_wt._handle_worker_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_wt._worker_tokens_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (plain backspace, kill-line) never clears _worker_tokens_search.matches "
          "-- Enter remains the sole recompute trigger")
    _reset_state('foo')
    mod_wt._worker_tokens_search.matches = [(0, 0), ('turn', 1)]
    mod_wt._worker_tokens_search.match_set = {(0, 0), ('turn', 1)}
    mod_wt._handle_worker_tokens_search_input('\x7f')
    check("matches survive plain backspace", mod_wt._worker_tokens_search.matches == [(0, 0), ('turn', 1)])
    mod_wt._handle_worker_tokens_search_input(mod_search_bar.KILL_LINE_CHAR)
    check("matches survive kill-line", mod_wt._worker_tokens_search.matches == [(0, 0), ('turn', 1)])


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
        output, _ = mod_wt._build_worker_tokens_output(_MONITOR)
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
        output, _ = mod_wt._build_worker_tokens_output(_MONITOR)
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
        output, _ = mod_wt._build_worker_tokens_output(_MONITOR)
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
        output, _ = mod_wt._build_worker_tokens_output(_MONITOR)
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


def test_esc_cancel_clears_state_bar_stays():
    print("\n[Esc] Cancel clears query/matches/selection; the bar itself is never hidden")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._worker_tokens_search.focused = True
    mod_wt._worker_tokens_search.matches = [(0, 0)]
    mod_wt._worker_tokens_search.match_set = {(0, 0)}
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 1, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 5, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    changed = mod_wt._handle_worker_tokens_search_cancel()
    check("cancel reports a change", changed)
    check("query cleared", mod_wt._worker_tokens_search.query == '')
    check("matches cleared", mod_wt._worker_tokens_search.matches == [] and mod_wt._worker_tokens_search.match_set == set())
    check("focused cleared", mod_wt._worker_tokens_search.focused is False)
    check("selection cleared", mod_wt._worker_tokens_search.sel_anchor is None)
    bar = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring")
    _reset_state('hello world')
    label = mod_wt._WT_SEARCH_BAR_LABEL
    mod_wt._handle_worker_tokens_mouse(0, len(label) + 2, 1, _MONITOR)
    mod_wt._handle_worker_tokens_mouse(32, len(label) + 7, 1, _MONITOR)
    mod_wt._handle_worker_tokens_search_release()
    bar = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring", '\033[7mello \033[27m' in bar)

    _reset_state('hello world')
    bar2 = mod_wt._render_worker_tokens_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)


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
        output, _ = mod_wt._build_worker_tokens_output(_MONITOR)
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


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P7 -- worker-tokens pane search bar + worker-switch header parity suite")
    print("=" * 70)
    test_state_shape_and_label()
    test_two_row_header_composition()
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
    test_light_red_bg_still_detected_when_call_is_also_a_match()
    test_n_N_jump_wraps_both_directions()
    test_esc_cancel_clears_state_bar_stays()
    test_render_reverse_video_bracket()
    test_sentinel_resolves_to_default_bg_not_empty_string()
    test_jump_to_match_moves_scroll_offset()
    test_worker_switch_resets_search_state_and_scroll()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p7_workers_pane_parity_test_{ts}.md'
    lines = [f"# P7 worker-tokens pane parity regression -- {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
