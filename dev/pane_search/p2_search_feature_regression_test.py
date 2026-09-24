# INFRASTRUCTURE
import sys
from pathlib import Path

from p2_search_feature_regression_cases import (
    test_search_bar_renders_at_row1,
    test_line_map_shift,
    test_collapsed_hit_marks_req_row,
    test_expanded_hit_marks_line,
    test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows,
    test_n_N_ordering,
    test_esc_clears_query_bar_stays,
    test_scroll_jump_clamps,
    test_flow_id_lazy_load_fix,
    test_utf8_multibyte_keypress,
    test_utf8_search_query_accumulation,
    test_kill_line_after_a_real_search_run,
)

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    'test_search_bar_renders_at_row1',
    'test_line_map_shift',
    'test_collapsed_hit_marks_req_row',
    'test_expanded_hit_marks_line',
    'test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows',
    'test_n_N_ordering',
    'test_esc_clears_query_bar_stays',
    'test_scroll_jump_clamps',
    'test_flow_id_lazy_load_fix',
    'test_utf8_multibyte_keypress',
    'test_utf8_search_query_accumulation',
    'test_kill_line_after_a_real_search_run',
]
_TITLE = 'P2 — proxy-pane search feature regression suite (M2)'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p2_search_feature_regression_test.md'

# ORCHESTRATOR

def run_probe_workflow():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


if __name__ == '__main__':
    run_probe_workflow()
