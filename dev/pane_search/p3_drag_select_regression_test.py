# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p3_drag_select_regression_fixtures import _RESULTS
from p3_drag_select_regression_cases import (
    test_col_to_index_ascii,
    test_col_to_index_wide_char,
    test_drag_select_copies_to_clipboard,
    test_plain_click_no_motion_no_clipboard,
    test_release_noop_without_active_drag,
    test_body_row_drag_never_arms_search_selection,
    test_click_elsewhere_clears_selection,
    test_new_input_clears_selection,
    test_backspace_deletes_active_selection,
    test_backspace_without_selection_still_trims_last_char,
    test_kill_line_empties_query,
    test_kill_line_ignores_active_selection,
    test_kill_line_not_silently_swallowed_by_isprintable_fallthrough,
    test_editing_never_clears_matches,
    test_esc_cancel_clears_selection,
    test_render_reverse_video_bracket,
    test_session_change_clears_selection,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P3 — proxy-pane search bar drag-to-select regression suite")
    print("=" * 70)
    test_col_to_index_ascii()
    test_col_to_index_wide_char()
    test_drag_select_copies_to_clipboard()
    test_plain_click_no_motion_no_clipboard()
    test_release_noop_without_active_drag()
    test_body_row_drag_never_arms_search_selection()
    test_click_elsewhere_clears_selection()
    test_new_input_clears_selection()
    test_backspace_deletes_active_selection()
    test_backspace_without_selection_still_trims_last_char()
    test_kill_line_empties_query()
    test_kill_line_ignores_active_selection()
    test_kill_line_not_silently_swallowed_by_isprintable_fallthrough()
    test_editing_never_clears_matches()
    test_esc_cancel_clears_selection()
    test_render_reverse_video_bracket()
    test_session_change_clears_selection()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p3_drag_select_regression_test_{ts}.md'
    lines = [f"# P3 drag-select regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
