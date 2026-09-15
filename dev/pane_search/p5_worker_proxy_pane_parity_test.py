"""
p5_worker_proxy_pane_parity_test.py — Regression guard for the worker-proxy pane reaching
search-bar parity with the proxy pane (rollout sub-milestone 3, process-docs/pane_search/).

worker_proxy_pane.py is the proxy pane's closest structural twin — same format_proxy_block/
render_turn pipeline (search kwargs already threaded through, previously defaulted off for this
pane specifically), same forwarded-log data model, same one-sweep reconstruct_all_messages
strategy, same flow_id-fixed _lazy_load_messages_forwarded. The NEW work this milestone covers:

  - 2-ROW HEADER: the search bar takes row 1 (uniform rule); the existing worker-switcher header
    (_format_worker_proxy_header, variable height, click-region table) shifts to row 2+.
    _worker_proxy_header_regions (rows relative to the header's OWN top, computed by the pure
    helper worker_proxy_helpers.py — untouched) get shifted by +_WP_SEARCH_BAR_LINES in
    _build_worker_proxy_output, same rebuild-then-shift pattern already used for
    worker_proxy_line_map/_worker_proxy_copy_rows. content_height/body_hover use
    total_header_lines = _WP_SEARCH_BAR_LINES + worker_header_lines, not the old header_lines
    alone.
  - row-1 press/motion/release drag-select, editor-style deletion (selection-delete Backspace,
    kill-line), n/N jump reusing the EXISTING _wp_just_expanded/worker_item_positions/
    scroll-clamp mechanism (same anchor for collapsed and expanded matches)
  - Enter (_worker_proxy_search_on_commit) always re-runs (no unchanged-query gate — proxy's
    convention, no main-pane-style gate ever existed here to correct); one-sweep
    reconstruct_all_messages merge by flow_id when _worker_proxy_log_path is set
  - WORKER-SWITCH RESET: _refresh_worker_proxy_data's existing worker-change branch (fires for
    BOTH digit-key and header-marker selection, same selection-file + force_reload convergence
    point) now also calls search_bar.handle_search_cancel(_worker_proxy_search) — mirrors
    pane.py's session-change reset and the same fix just landed on the main pane. A stale
    .matches list of entry_idx values would otherwise point into the log just switched away
    from.

Uses REAL src.proxy_display.worker_proxy_pane functions against synthetic entries/workers —
not mocks. importlib.import_module used throughout (dev/ scripts may not use a literal
'from src.' import line).

Run: ./venv/bin/python dev/pane_search/p5_worker_proxy_pane_parity_test.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p5_worker_proxy_pane_parity_fixtures import _RESULTS
from p5_worker_proxy_pane_parity_cases_mechanics import (
    test_state_shape,
    test_two_row_header_composition_and_shifts,
    test_header_marker_click_still_selects_worker_at_shifted_row,
    test_row1_press_focuses_and_arms_drag,
    test_drag_select_copies_to_clipboard,
    test_plain_click_no_motion_no_clipboard,
    test_release_noop_without_active_drag,
    test_body_row_click_clears_selection,
    test_body_row_drag_never_arms_search_selection,
    test_new_input_clears_selection,
    test_backspace_deletes_active_selection,
    test_backspace_without_selection_still_trims_last_char,
    test_kill_line_empties_query,
    test_editing_never_clears_matches,
    test_render_reverse_video_bracket,
)
from p5_worker_proxy_pane_parity_cases_search import (
    test_enter_runs_real_search_no_log_path,
    test_enter_always_reruns_not_gated_on_unchanged_query,
    test_enter_triggers_reconstruction_merge_when_log_path_set,
    test_n_N_jump_wraps_both_directions,
    test_esc_cancel_clears_state_bar_stays,
    test_worker_switch_resets_search_state,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P5 — worker-proxy pane search bar parity regression suite")
    print("=" * 70)
    test_state_shape()
    test_two_row_header_composition_and_shifts()
    test_header_marker_click_still_selects_worker_at_shifted_row()
    test_row1_press_focuses_and_arms_drag()
    test_drag_select_copies_to_clipboard()
    test_plain_click_no_motion_no_clipboard()
    test_release_noop_without_active_drag()
    test_body_row_click_clears_selection()
    test_body_row_drag_never_arms_search_selection()
    test_new_input_clears_selection()
    test_backspace_deletes_active_selection()
    test_backspace_without_selection_still_trims_last_char()
    test_kill_line_empties_query()
    test_editing_never_clears_matches()
    test_enter_runs_real_search_no_log_path()
    test_enter_always_reruns_not_gated_on_unchanged_query()
    test_enter_triggers_reconstruction_merge_when_log_path_set()
    test_n_N_jump_wraps_both_directions()
    test_esc_cancel_clears_state_bar_stays()
    test_render_reverse_video_bracket()
    test_worker_switch_resets_search_state()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p5_worker_proxy_pane_parity_test_{ts}.md'
    lines = [f"# P5 worker-proxy pane parity regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
