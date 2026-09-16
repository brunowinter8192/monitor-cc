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
