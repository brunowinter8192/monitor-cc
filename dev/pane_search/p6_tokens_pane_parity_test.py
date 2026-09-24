# INFRASTRUCTURE
import sys
from pathlib import Path

from p6_tokens_pane_parity_cases_mechanics import (
    test_state_shape_and_label,
    test_search_bar_row1_renders_no_arrows,
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
from p6_tokens_pane_parity_cases_matching import (
    test_call_level_match_collapsed_container_marked,
    test_call_level_match_expanded_substring_marked,
    test_turn_level_match,
    test_n_N_jump_wraps_both_directions,
    test_sentinel_resolves_to_default_bg_not_empty_string,
    test_light_red_bg_still_detected_when_call_is_also_a_match,
    test_jump_to_match_moves_scroll_offset,
    test_session_change_resets_search_state,
)

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    'test_state_shape_and_label',
    'test_search_bar_row1_renders_no_arrows',
    'test_row1_press_focuses_and_arms_drag',
    'test_drag_select_copies_to_clipboard',
    'test_plain_click_no_motion_no_clipboard',
    'test_release_noop_without_active_drag',
    'test_body_click_clears_selection',
    'test_body_drag_never_arms_search_selection',
    'test_new_input_clears_selection',
    'test_backspace_deletes_active_selection',
    'test_backspace_without_selection_still_trims_last_char',
    'test_kill_line_empties_query',
    'test_editing_never_clears_matches',
    'test_call_level_match_collapsed_container_marked',
    'test_call_level_match_expanded_substring_marked',
    'test_turn_level_match',
    'test_n_N_jump_wraps_both_directions',
    'test_esc_cancel_clears_state_bar_stays',
    'test_render_reverse_video_bracket',
    'test_sentinel_resolves_to_default_bg_not_empty_string',
    'test_light_red_bg_still_detected_when_call_is_also_a_match',
    'test_jump_to_match_moves_scroll_offset',
    'test_session_change_resets_search_state',
]
_TITLE = 'P6 — tokens pane search bar parity regression suite'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p6_tokens_pane_parity_test.md'

# ORCHESTRATOR

def run_probe_workflow():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


if __name__ == '__main__':
    run_probe_workflow()
