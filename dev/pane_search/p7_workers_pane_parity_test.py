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
import sys
from datetime import datetime
from pathlib import Path

from p7_workers_pane_parity_fixtures import _RESULTS
from p7_workers_pane_parity_cases_mechanics import (
    test_state_shape_and_label,
    test_two_row_header_composition,
    test_row1_press_focuses_and_arms_drag,
    test_drag_select_copies_to_clipboard,
    test_plain_click_no_motion_no_clipboard,
    test_release_noop_without_active_drag,
    test_body_click_clears_selection,
    test_body_drag_never_arms_search_selection,
    test_new_input_clears_selection,
    test_backspace_deletes_active_selection,
    test_backspace_without_selection_still_trims_last_char,
    test_kill_line_empties_query,
    test_editing_never_clears_matches,
    test_esc_cancel_clears_state_bar_stays,
    test_render_reverse_video_bracket,
)
from p7_workers_pane_parity_cases_matching import (
    test_call_level_match_collapsed_container_marked,
    test_call_level_match_expanded_substring_marked,
    test_turn_level_match,
    test_light_red_bg_still_detected_when_call_is_also_a_match,
    test_n_N_jump_wraps_both_directions,
    test_sentinel_resolves_to_default_bg_not_empty_string,
    test_jump_to_match_moves_scroll_offset,
    test_worker_switch_resets_search_state_and_scroll,
)

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
