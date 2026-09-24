# INFRASTRUCTURE
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from dev.dual_log_cli.tests.reqs_pane_numbering_basic_checks import (
    test_continues_are_found_and_haiku_is_not, test_create_sharing_a_start_index_is_its_own_req,
    test_fallback_when_transcript_unresolved, test_gap_pairs_two_continues_of_one_turn, test_msgs_uses_pane_numbers,
    test_no_output_at_all_prints_one_line, test_numbering_annotates_creates_and_continues,
    test_owner_rule_prefers_mapped_boundary, test_reqs_lists_every_main_thread_request,
    test_sessions_without_output_are_hidden)
from dev.dual_log_cli.tests.reqs_pane_numbering_ownership_checks import (
    test_expand_req_errors_and_cli, test_expand_req_selects_reply_and_returned_result,
    test_msg_start_of_creates_and_continues, test_msgs_prints_continue_separators,
    test_req_range_covers_own_group_and_next, test_unlocated_continues_own_no_msgs)
from dev.dual_log_cli.tests.reqs_pane_numbering_unmapped_checks import (
    test_non_200_status_is_visible_on_the_req_line, test_unmapped_req_sits_in_its_turn_by_send_time,
    test_unmapped_req_stays_out_of_gap_pairs)
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_continues_are_found_and_haiku_is_not',
    'test_numbering_annotates_creates_and_continues',
    'test_reqs_lists_every_main_thread_request',
    'test_gap_pairs_two_continues_of_one_turn',
    'test_msgs_uses_pane_numbers',
    'test_owner_rule_prefers_mapped_boundary',
    'test_fallback_when_transcript_unresolved',
    'test_create_sharing_a_start_index_is_its_own_req',
    'test_sessions_without_output_are_hidden',
    'test_no_output_at_all_prints_one_line',
    'test_msg_start_of_creates_and_continues',
    'test_req_range_covers_own_group_and_next',
    'test_unlocated_continues_own_no_msgs',
    'test_msgs_prints_continue_separators',
    'test_expand_req_selects_reply_and_returned_result',
    'test_expand_req_errors_and_cli',
    'test_unmapped_req_sits_in_its_turn_by_send_time',
    'test_unmapped_req_stays_out_of_gap_pairs',
    'test_non_200_status_is_visible_on_the_req_line',
]

# ORCHESTRATOR

def test_reqs_pane_numbering_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_reqs_pane_numbering')

# FUNCTIONS



if __name__ == '__main__':
    sys.exit(test_reqs_pane_numbering_workflow())
