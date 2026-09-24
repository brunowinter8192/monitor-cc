# INFRASTRUCTURE
import sys
from pathlib import Path

from p8_warnings_gpu_news_parity_cases_warnings import (
    test_warnings_state_shape,
    test_warnings_dim_yellow_bg_already_used_in_not_startswith,
    test_warnings_search_bar_row1_and_refresh_header_shifted,
    test_warnings_row1_press_focuses_and_arms_drag,
    test_warnings_drag_select_copies_to_clipboard,
    test_warnings_plain_click_no_clipboard_and_body_clears_selection,
    test_warnings_editing_mechanics,
    test_warnings_collapsed_container_mark_and_expanded_substring_mark,
    test_warnings_sentinel_resolves_to_default_bg_not_empty_string,
    test_warnings_n_N_cycles_without_touching_scroll,
    test_warnings_esc_cancel_and_reverse_video,
)
from p8_warnings_gpu_news_parity_cases_gpu import (
    test_gpu_state_shape,
    test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally,
    test_gpu_row1_click_focuses_search_bar,
    test_gpu_drag_select_and_editing,
    test_gpu_highlight_only_match_no_sentinel_needed,
    test_gpu_n_N_cycles_current_idx_no_scroll_infra,
    test_gpu_esc_cancel_bar_stays,
)
from p8_warnings_gpu_news_parity_cases_news import (
    test_news_state_shape,
    test_news_render_pane_stays_unshifted,
    test_news_highlight_only_match,
    test_news_drag_select_and_n_N,
    test_news_esc_cancel_bar_stays,
)

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    'test_warnings_state_shape',
    'test_warnings_dim_yellow_bg_already_used_in_not_startswith',
    'test_warnings_search_bar_row1_and_refresh_header_shifted',
    'test_warnings_row1_press_focuses_and_arms_drag',
    'test_warnings_drag_select_copies_to_clipboard',
    'test_warnings_plain_click_no_clipboard_and_body_clears_selection',
    'test_warnings_editing_mechanics',
    'test_warnings_collapsed_container_mark_and_expanded_substring_mark',
    'test_warnings_sentinel_resolves_to_default_bg_not_empty_string',
    'test_warnings_n_N_cycles_without_touching_scroll',
    'test_warnings_esc_cancel_and_reverse_video',
    'test_gpu_state_shape',
    'test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally',
    'test_gpu_row1_click_focuses_search_bar',
    'test_gpu_drag_select_and_editing',
    'test_gpu_highlight_only_match_no_sentinel_needed',
    'test_gpu_n_N_cycles_current_idx_no_scroll_infra',
    'test_gpu_esc_cancel_bar_stays',
    'test_news_state_shape',
    'test_news_render_pane_stays_unshifted',
    'test_news_highlight_only_match',
    'test_news_drag_select_and_n_N',
    'test_news_esc_cancel_bar_stays',
]
_TITLE = 'P8 -- warnings + gpu + news panes search bar parity regression suite'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p8_warnings_gpu_news_parity_test.md'

# ORCHESTRATOR

def run_probe_workflow():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


if __name__ == '__main__':
    run_probe_workflow()
