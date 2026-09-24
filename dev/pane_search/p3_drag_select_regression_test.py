# INFRASTRUCTURE
import sys
from pathlib import Path

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

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    'test_col_to_index_ascii',
    'test_col_to_index_wide_char',
    'test_drag_select_copies_to_clipboard',
    'test_plain_click_no_motion_no_clipboard',
    'test_release_noop_without_active_drag',
    'test_body_row_drag_never_arms_search_selection',
    'test_click_elsewhere_clears_selection',
    'test_new_input_clears_selection',
    'test_backspace_deletes_active_selection',
    'test_backspace_without_selection_still_trims_last_char',
    'test_kill_line_empties_query',
    'test_kill_line_ignores_active_selection',
    'test_kill_line_not_silently_swallowed_by_isprintable_fallthrough',
    'test_editing_never_clears_matches',
    'test_esc_cancel_clears_selection',
    'test_render_reverse_video_bracket',
    'test_session_change_clears_selection',
]
_TITLE = 'P3 — proxy-pane search bar drag-to-select regression suite'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p3_drag_select_regression_test.md'

# ORCHESTRATOR

def run_probe_workflow():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


if __name__ == '__main__':
    run_probe_workflow()
