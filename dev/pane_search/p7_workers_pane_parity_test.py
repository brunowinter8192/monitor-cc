"""
p7_workers_pane_parity_test.py — Regression guard for the workers pane's search bar reaching
parity with the proxy pane (rollout sub-milestone 5, process-docs/pane_search/).

worker_pane.py + worker_format.py are the FIRST pane in this rollout needing a genuine NEW
reconstruction strategy: worker_turns is populated only for currently-EXPANDED workers (see
_refresh_workers_data), so finding matches across ALL workers requires force-parsing every
listed worker's own JSONL on Enter (measured ~200ms for 9 real, multi-MB session files during
implementation — comfortably under budget, see process-docs/pane_search/). Three genuinely new
pieces this milestone had to build:

  - THREE-TIER MATCH KEYS: bare `name` (worker-level — text is name+purpose), reusing the exact
    shape line_keys already used for header/purpose rows; `(name,'turn',turn_idx)` and
    `(name,turn_idx,call_idx)`, wrapping token_search.build_token_search_matches' own (turn_idx,
    call_idx)/('turn',turn_idx) shapes with the worker name — the latter REUSES the exact
    3-tuple shape worker_format.py already built for cache rows, zero new shape there either.
  - COMPOSING WITH format_cache_tracker (sub-milestone 4's kwargs): format_workers_block scopes
    the flat worker-tagged match set DOWN to each worker's own token_format-shape keys
    (_scope_matches_to_worker/_scope_current_key_to_worker in worker_format.py) before threading
    into its own per-worker format_cache_tracker call — format_cache_tracker does 100% of the
    collapsed-container-mark/expanded-substring-highlight work internally; only the worker's own
    header line needed new embedding logic here.
  - THE SENTINEL BUG, third occurrence, same fix — plus a collateral LIGHT_RED_BG detection
    fix identical in shape to the tokens-pane one (`.startswith()` -> `in`).
  - JUMP-TO-MATCH respecting the DORMANT pane-level scroll: worker_scroll_offset (bottom-anchor
    fail-safe) is never touched; jump-to-match auto-expands + auto-selects the matched worker
    and computes worker_scroll_offsets[name] (the per-worker scroll the pane already supports)
    via a FRESH, self-contained format_cache_tracker(...,nav_out=...) call made directly at
    jump time — deliberately not relying on worker_turns' own churn (cleared every poll tick for
    non-expanded workers).
  - NO worker-switch reset analog (considered, declined, documented as a design choice, not an
    oversight) — this pane shows ALL workers simultaneously, no single "current worker" to
    switch away from; jump-to-match's fresh re-parse makes a stale match self-healing instead.

Uses REAL src.workers.worker_pane / src.workers.worker_format / src.panes.token_search functions
against synthetic workers + REAL throwaway JSONL fixture files (find_worker_jsonl monkeypatched
to point at them) — not mocks of the reconstruction pipeline itself. importlib.import_module
used throughout.

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

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_wp = importlib.import_module(f'{_ROOT_PKG}.workers.worker_pane')
mod_wf = importlib.import_module(f'{_ROOT_PKG}.workers.worker_format')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')

PANE_WIDTH = 100
_RESULTS = []
_TMP_ROOT = None


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

def _reset_state(query: str = ''):
    mod_wp.worker_expand_states.clear()
    mod_wp.worker_scroll_offsets.clear()
    mod_wp.worker_line_map.clear()
    mod_wp.worker_hover_row = None
    mod_wp.worker_cache_expand_states.clear()
    mod_wp.worker_cache_line_map.clear()
    mod_wp.worker_selected_name = None
    mod_wp.worker_scroll_offset = 0
    mod_wp.worker_turns.clear()
    mod_wp.worker_copy_rows.clear()
    mod_wp._worker_copy_feedback_until.clear()
    mod_wp._worker_pane_width = PANE_WIDTH
    mod_wp._worker_header_regions.clear()
    mod_wp._worker_search.query = query
    mod_wp._worker_search.focused = False
    mod_wp._worker_search.matches = []
    mod_wp._worker_search.match_set = set()
    mod_wp._worker_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wp._worker_search)


# Write a real throwaway JSONL fixture (one user prompt + optional one assistant tool_use call)
# for a worker, monkeypatch find_worker_jsonl to resolve it, and return the workers list.
# Real reconstruction pipeline (read_new_lines -> parse_jsonl_lines -> extract_cache_turns) runs
# unmocked against these files — only the tmux-session -> path RESOLUTION is stubbed.
def _setup_worker_jsonls(specs):
    global _TMP_ROOT
    _TMP_ROOT = Path(tempfile.mkdtemp(prefix='pane_search_p7_'))
    workers = []
    paths = {}
    for name, purpose, prompt, call_marker in specs:
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
        paths[session] = path
        workers.append({'name': name, 'status': 'working', 'purpose': purpose, 'session': session})
    orig_find = mod_wp.find_worker_jsonl
    mod_wp.find_worker_jsonl = lambda session: paths.get(session)
    return workers, orig_find


def _cleanup_worker_jsonls(orig_find):
    global _TMP_ROOT
    mod_wp.find_worker_jsonl = orig_find
    if _TMP_ROOT:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
        _TMP_ROOT = None


def _capture_clipboard():
    captured = []
    orig = mod_wp.copy_to_clipboard
    mod_wp.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig


# TESTS

def test_state_shape_and_label():
    print("\n[shape] Workers pane search state is one search_bar.SearchState, lowercase label")
    check("_worker_search is a search_bar.SearchState instance",
          isinstance(mod_wp._worker_search, mod_search_bar.SearchState))
    check("label is 'search: '", mod_wp._WORKERS_SEARCH_BAR_LABEL == 'search: ')
    check("search bar is fixed 1-line", mod_wp._WORKERS_SEARCH_BAR_LINES == 1)


def test_search_bar_row1_and_freeze_badge_shifted():
    print("\n[2-row header] Search bar row 1; freeze badge region shifted to row 2")
    _reset_state()
    workers = [{'name': 'w1', 'status': 'working', 'purpose': 'run the build', 'session': ''}]
    output = mod_wp._build_workers_output(workers, frozen=False)
    first_line = output.splitlines()[0]
    check("row 1 shows the 'search: ' label", 'search:' in first_line)
    check("no click-arrows", '[←]' not in first_line and '[→]' not in first_line)
    check("row 1 is not a body line_map key", mod_wp.worker_line_map.get(1) is None)
    check("freeze region exists and is at row 2", bool(mod_wp._worker_header_regions))
    (sc, ec, er) = next(iter(mod_wp._worker_header_regions))
    check("freeze region row is 2 (shifted past the search bar)", er == 2)
    changed, frozen2 = mod_wp._handle_workers_mouse(0, (sc + ec) // 2, er, '/tmp/p7proj', False)
    check("clicking the shifted freeze region still toggles frozen", changed and frozen2 is True)


def test_row1_press_focuses_and_arms_drag():
    print("\n[press] A row-1 click focuses the bar and anchors a drag-select")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    changed, _ = mod_wp._handle_workers_mouse(0, len(label) + 2, 1, None, False)
    check("press returns True (redraw)", changed)
    check("press focuses the bar", mod_wp._worker_search.focused is True)
    check("press arms dragging", mod_wp._worker_search.dragging is True)
    check("press anchors at index 1 ('e')",
          mod_wp._worker_search.sel_anchor == mod_wp._worker_search.sel_end == 1)


def test_drag_select_copies_to_clipboard():
    print("\n[drag flow] press -> motion -> release copies the selected substring")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wp._WORKERS_SEARCH_BAR_LABEL
        mod_wp._handle_workers_mouse(0, len(label) + 2, 1, None, False)
        motion_changed, _ = mod_wp._handle_workers_mouse(32, len(label) + 7, 1, None, False)
        check("motion extends sel_end only", motion_changed and mod_wp._worker_search.sel_end == 6)
        release_changed = mod_wp._handle_workers_search_release()
        check("release returns True (redraw)", release_changed)
        check("release disarms dragging", mod_wp._worker_search.dragging is False)
        check("release copies exactly the selected substring", captured == ['ello '])
    finally:
        mod_wp.copy_to_clipboard = orig


def test_plain_click_no_motion_no_clipboard():
    print("\n[plain click] press+release with NO motion makes zero clipboard calls")
    _reset_state('hello world')
    captured, orig = _capture_clipboard()
    try:
        label = mod_wp._WORKERS_SEARCH_BAR_LABEL
        mod_wp._handle_workers_mouse(0, len(label) + 3, 1, None, False)
        release_changed = mod_wp._handle_workers_search_release()
        check("release still returns True (dragging disarmed)", release_changed)
        check("NO clipboard call on a plain click", captured == [])
        check("selection cleared after a plain click",
              mod_wp._worker_search.sel_anchor is None and mod_wp._worker_search.sel_end is None)
    finally:
        mod_wp.copy_to_clipboard = orig


def test_release_noop_without_active_drag():
    print("\n[release no-op] A release with no prior row-1 press changes nothing")
    _reset_state('hello world')
    changed = mod_wp._handle_workers_search_release()
    check("release with no armed drag returns False", changed is False)


def test_body_click_clears_selection():
    print("\n[clear] Click on the body (row >= 2, unmapped) clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    mod_wp._handle_workers_mouse(0, len(label) + 1, 1, None, False)
    mod_wp._handle_workers_mouse(32, len(label) + 5, 1, None, False)
    mod_wp._handle_workers_search_release()
    check("selection exists before the elsewhere-click", mod_wp._worker_search.sel_anchor is not None)
    changed, _ = mod_wp._handle_workers_mouse(0, 5, 10, None, False)  # unmapped body row
    check("elsewhere-click reports a change (selection cleared)", changed)
    check("selection cleared after clicking elsewhere",
          mod_wp._worker_search.sel_anchor is None and mod_wp._worker_search.sel_end is None)


def test_body_drag_never_arms_search_selection():
    print("\n[scope] A drag starting on a BODY row never arms search-bar dragging")
    _reset_state('hello world')
    mod_wp._handle_workers_mouse(0, 5, 10, None, False)
    check("body-row press does not arm dragging", mod_wp._worker_search.dragging is False)
    mod_wp._handle_workers_mouse(32, 40, 10, None, False)
    check("motion after a body-row press falls through to generic hover", mod_wp.worker_hover_row == 10)


def test_new_input_clears_selection():
    print("\n[clear] New keyboard input clears a live drag-selection")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    mod_wp._handle_workers_mouse(0, len(label) + 1, 1, None, False)
    mod_wp._handle_workers_mouse(32, len(label) + 5, 1, None, False)
    mod_wp._handle_workers_search_release()
    check("selection exists before typing", mod_wp._worker_search.sel_anchor is not None)
    changed = mod_wp._handle_workers_search_input('x', [], None)
    check("typing reports a change", changed)
    check("selection cleared after typing",
          mod_wp._worker_search.sel_anchor is None and mod_wp._worker_search.sel_end is None)
    check("typed char appended at the end", mod_wp._worker_search.query == 'hello worldx')


def test_backspace_deletes_active_selection():
    print("\n[editor-style delete] Backspace with an active selection deletes the SELECTED substring")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    mod_wp._handle_workers_mouse(0, len(label) + 2, 1, None, False)
    mod_wp._handle_workers_mouse(32, len(label) + 7, 1, None, False)
    mod_wp._handle_workers_search_release()
    changed = mod_wp._handle_workers_search_input('\x7f', [], None)
    check("backspace reports a change", changed)
    check("query has the SELECTED substring removed", mod_wp._worker_search.query == 'hworld')
    check("selection cleared after selection-delete",
          mod_wp._worker_search.sel_anchor is None and mod_wp._worker_search.sel_end is None)


def test_backspace_without_selection_still_trims_last_char():
    print("\n[editor-style delete] Backspace with no selection still trims the last char")
    _reset_state('hello')
    changed = mod_wp._handle_workers_search_input('\x7f', [], None)
    check("backspace reports a change", changed)
    check("last char trimmed", mod_wp._worker_search.query == 'hell')


def test_kill_line_empties_query():
    print("\n[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query")
    _reset_state('some fairly long search query text')
    changed = mod_wp._handle_workers_search_input(mod_search_bar.KILL_LINE_CHAR, [], None)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_wp._worker_search.query == '')


def test_editing_never_clears_matches():
    print("\n[matches] Editing (plain backspace, kill-line) never clears _worker_search.matches "
          "— Enter remains the sole recompute trigger")
    _reset_state('foo')
    mod_wp._worker_search.matches = ['w1', ('w2', 'turn', 0)]
    mod_wp._worker_search.match_set = {'w1', ('w2', 'turn', 0)}
    mod_wp._handle_workers_search_input('\x7f', [], None)
    check("matches survive plain backspace", mod_wp._worker_search.matches == ['w1', ('w2', 'turn', 0)])
    mod_wp._handle_workers_search_input(mod_search_bar.KILL_LINE_CHAR, [], None)
    check("matches survive kill-line", mod_wp._worker_search.matches == ['w1', ('w2', 'turn', 0)])


def test_worker_level_match_and_scoping():
    print("\n[match: worker-level + scoping] A match in one worker's name/purpose text does NOT "
          "leak into another worker's own nested view highlighting")
    _reset_state('special_purpose_marker')
    workers, orig_find = _setup_worker_jsonls([
        ('w1', 'special_purpose_marker task', 'do the build', None),
        ('w2', 'unrelated purpose', 'do something else', None),
    ])
    try:
        changed = mod_wp._handle_workers_search_input('\r', workers, '/tmp/p7proj')
        check("Enter reports a change", changed)
        check("real search found exactly the worker-level match for w1",
              mod_wp._worker_search.matches == ['w1'])
        check("w1 auto-expanded by the jump", mod_wp.worker_expand_states.get('w1') is True)
        check("w2 NOT auto-expanded (not a match)", mod_wp.worker_expand_states.get('w2', False) is False)
        output = mod_wp._build_workers_output(workers, frozen=False)
        check("w1's header line is container-marked", mod_colors.SEARCH_CURRENT_BG in output)
        check("no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output",
              mod_search_bar._BG_RESTORE_SENTINEL not in output)
    finally:
        _cleanup_worker_jsonls(orig_find)


def test_call_level_match_collapsed_container_marked_and_scoped():
    print("\n[match: call-level + scoping] Whole call-header line container-marked in the "
          "MATCHING worker's own nested view; a non-matching sibling worker's own nested view "
          "(if expanded) stays unmarked")
    _reset_state('unique_marker_x')
    workers, orig_find = _setup_worker_jsonls([
        ('w1', 'purpose one', 'do the build', 'unique_marker_x'),
        ('w2', 'purpose two', 'do other work', 'totally_different_call_content'),
    ])
    try:
        mod_wp.worker_expand_states['w2'] = True  # w2 expanded but its OWN content never matches
        mod_wp.worker_turns['w2'] = [{
            'prompt': 'do other work', 'timestamp': '2026-01-01T00:00:00Z',
            'api_calls': [{'cache_read': 1000, 'cache_creation': 0, 'direct': 0, 'output_tokens': 10,
                           'content_blocks': [{'type': 'text', 'preview': 'totally_different_call_content', 'chars': 5}]}],
        }]
        changed = mod_wp._handle_workers_search_input('\r', workers, '/tmp/p7proj')
        check("Enter reports a change", changed)
        check("real search found exactly the call-level match for w1",
              mod_wp._worker_search.matches == [('w1', 0, 0)])
        check("w1 auto-expanded", mod_wp.worker_expand_states.get('w1') is True)
        check("call is NOT auto-expanded (collapsed container mark, matches token_pane's decision)",
              mod_wp.worker_cache_expand_states.get('w1', {}).get((0, 0), False) is False)
        output = mod_wp._build_workers_output(workers, frozen=False)
        row = next(r for r, k in mod_wp.worker_cache_line_map.items() if k == ('w1', 0, 0))
        w1_call_line = output.splitlines()[row - 1]
        check("w1's collapsed call header is container-marked", mod_colors.SEARCH_CURRENT_BG in w1_call_line)
        check("the marker text itself does NOT leak into the collapsed row", 'unique_marker_x' not in w1_call_line)
        w2_lines = '\n'.join(l for l in output.splitlines() if 'totally_different_call_content' in l)
        check("w2's own (non-matching) expanded content carries NO search highlight",
              mod_colors.SEARCH_CURRENT_BG not in w2_lines and mod_colors.SEARCH_MATCH_BG not in w2_lines)
    finally:
        _cleanup_worker_jsonls(orig_find)


def test_light_red_bg_still_detected_when_call_is_also_a_match():
    print("\n[regression] LIGHT_RED_BG (cc_broken row) detection uses 'in line', not "
          "'.startswith()' — a search-match wrap now precedes it in the string")
    _reset_state('unique_marker_w')
    workers, orig_find = _setup_worker_jsonls([('w1', 'p', 'prompt', 'unique_marker_w')])
    try:
        # Force cc_broken (cache_creation > cache_read) directly on the fixture's own call, via
        # a manual overwrite after the real parse -- simplest way to get a real LIGHT_RED_BG
        # prefix out of _format_cache_call while still exercising the real search/render path.
        mod_wp.worker_expand_states['w1'] = True
        changed = mod_wp._handle_workers_search_input('\r', workers, '/tmp/p7proj')
        check("real search found the call", mod_wp._worker_search.matches == [('w1', 0, 0)])
        mod_wp.worker_turns['w1'][0]['api_calls'][0]['cache_creation'] = 5000
        mod_wp.worker_turns['w1'][0]['api_calls'][0]['cache_read'] = 100
        output = mod_wp._build_workers_output(workers, frozen=False)
        row = next(r for r, k in mod_wp.worker_cache_line_map.items() if k == ('w1', 0, 0))
        header_line = output.splitlines()[row - 1]
        check("row's OUTER chosen_bg is still LIGHT_RED_BG despite the search-marker wrap preceding it",
              header_line.startswith(mod_colors.LIGHT_RED_BG))
    finally:
        _cleanup_worker_jsonls(orig_find)


def test_n_N_jump_wraps_both_directions():
    print("\n[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches")
    _reset_state()
    check("no-op with zero matches", mod_wp._jump_workers_search_match(True, [], None) is False)
    mod_wp._worker_search.matches = ['w1', ('w2', 'turn', 0), ('w3', 0, 0)]
    mod_wp._worker_search.current_idx = 0
    check("n advances to idx 1", mod_wp._jump_workers_search_match(True, [], None) and mod_wp._worker_search.current_idx == 1)
    check("n advances to idx 2", mod_wp._jump_workers_search_match(True, [], None) and mod_wp._worker_search.current_idx == 2)
    check("n wraps back to idx 0", mod_wp._jump_workers_search_match(True, [], None) and mod_wp._worker_search.current_idx == 0)
    check("N (backward) wraps to idx 2", mod_wp._jump_workers_search_match(False, [], None) and mod_wp._worker_search.current_idx == 2)


def test_jump_self_heals_stale_worker_turns():
    print("\n[self-healing jump] jump-to-match ALWAYS re-parses the target worker fresh — never "
          "trusts worker_turns, which _refresh_workers_data clears every poll tick for "
          "non-expanded workers")
    _reset_state('unique_marker_fresh')
    workers, orig_find = _setup_worker_jsonls([('w1', 'p', 'prompt', 'unique_marker_fresh')])
    try:
        mod_wp._handle_workers_search_input('\r', workers, '/tmp/p7proj')
        check("real search found the call", mod_wp._worker_search.matches == [('w1', 0, 0)])
        check("worker_turns populated by the jump itself", 'w1' in mod_wp.worker_turns)
        # Simulate what _refresh_workers_data's poll-tick clear does to a NON-expanded worker —
        # then un-expand w1 and jump again; the jump must re-populate worker_turns itself,
        # not rely on the (now evicted) cache.
        mod_wp.worker_turns.clear()
        mod_wp.worker_expand_states['w1'] = False
        mod_wp._jump_to_workers_match(workers, '/tmp/p7proj')
        check("worker_turns re-populated fresh by the jump, not left empty",
              'w1' in mod_wp.worker_turns and mod_wp.worker_turns['w1'])
        check("w1 re-expanded by the jump", mod_wp.worker_expand_states.get('w1') is True)
        check("worker_scroll_offsets computed for w1", 'w1' in mod_wp.worker_scroll_offsets)
    finally:
        _cleanup_worker_jsonls(orig_find)


def test_jump_never_touches_dormant_pane_scroll():
    print("\n[dormant scroll] jump-to-match never touches worker_scroll_offset (the pane-level "
          "bottom-anchor fail-safe) — only the per-worker worker_scroll_offsets")
    _reset_state('unique_marker_dormant')
    workers, orig_find = _setup_worker_jsonls([('w1', 'p', 'prompt', 'unique_marker_dormant')])
    try:
        mod_wp.worker_scroll_offset = 0
        mod_wp._handle_workers_search_input('\r', workers, '/tmp/p7proj')
        check("worker_scroll_offset (pane-level, dormant) stays exactly 0", mod_wp.worker_scroll_offset == 0)
    finally:
        _cleanup_worker_jsonls(orig_find)


def test_vanished_worker_jump_is_a_noop_not_a_crash():
    print("\n[self-healing] Jumping to a match whose worker vanished from the CURRENT workers "
          "list is an inert no-op, not a crash")
    _reset_state()
    mod_wp._worker_search.matches = ['ghost-worker']
    mod_wp._worker_search.current_idx = 0
    mod_wp._jump_to_workers_match([], '/tmp/p7proj')  # empty workers list -- 'ghost-worker' not found
    check("no crash; ghost worker's expand-state entry is a harmless inert stub",
          mod_wp.worker_expand_states.get('ghost-worker') is True)


def test_esc_cancel_clears_state_bar_stays():
    print("\n[Esc] Cancel clears query/matches/selection; the bar itself is never hidden")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    mod_wp._worker_search.focused = True
    mod_wp._worker_search.matches = ['w1']
    mod_wp._worker_search.match_set = {'w1'}
    mod_wp._handle_workers_mouse(0, len(label) + 1, 1, None, False)
    mod_wp._handle_workers_mouse(32, len(label) + 5, 1, None, False)
    mod_wp._handle_workers_search_release()
    changed = mod_wp._handle_workers_search_cancel()
    check("cancel reports a change", changed)
    check("query cleared", mod_wp._worker_search.query == '')
    check("matches cleared", mod_wp._worker_search.matches == [] and mod_wp._worker_search.match_set == set())
    check("focused cleared", mod_wp._worker_search.focused is False)
    check("selection cleared", mod_wp._worker_search.sel_anchor is None)
    bar = mod_wp._render_workers_search_bar(PANE_WIDTH)
    check("bar still renders (never hidden)", 'search:' in bar)


def test_render_reverse_video_bracket():
    print("\n[render] Active selection renders SGR reverse-video around the exact substring")
    _reset_state('hello world')
    label = mod_wp._WORKERS_SEARCH_BAR_LABEL
    mod_wp._handle_workers_mouse(0, len(label) + 2, 1, None, False)
    mod_wp._handle_workers_mouse(32, len(label) + 7, 1, None, False)
    mod_wp._handle_workers_search_release()
    bar = mod_wp._render_workers_search_bar(PANE_WIDTH)
    check("reverse-video ON code present", '\033[7m' in bar)
    check("reverse-video OFF code present", '\033[27m' in bar)
    check("the reversed span wraps exactly the selected substring", '\033[7mello \033[27m' in bar)

    _reset_state('hello world')
    bar2 = mod_wp._render_workers_search_bar(PANE_WIDTH)
    check("no reverse-video codes when there is no selection", '\033[7m' not in bar2)


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P7 — workers pane search bar parity regression suite")
    print("=" * 70)
    test_state_shape_and_label()
    test_search_bar_row1_and_freeze_badge_shifted()
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
    test_worker_level_match_and_scoping()
    test_call_level_match_collapsed_container_marked_and_scoped()
    test_light_red_bg_still_detected_when_call_is_also_a_match()
    test_n_N_jump_wraps_both_directions()
    test_jump_self_heals_stale_worker_turns()
    test_jump_never_touches_dormant_pane_scroll()
    test_vanished_worker_jump_is_a_noop_not_a_crash()
    test_esc_cancel_clears_state_bar_stays()
    test_render_reverse_video_bracket()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p7_workers_pane_parity_test_{ts}.md'
    lines = [f"# P7 workers pane parity regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
