"""Unit tests for CC 2.1.176 background-launch-ack strip (Item 4).

Fixtures: launch-ack as tool_result string AND as standalone text block.
Marker: 'running in background with ID'.

Run from project root:
    ./venv/bin/python dev/proxy_176_bg_launch_ack_tests.py
"""
# INFRASTRUCTURE
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from proxy_176_bg_launch_ack_cases import (
    test_tool_result_str_content,
    test_text_block_content,
    test_str_message_content,
    test_tool_result_list_content,
    test_non_matching_tool_result_untouched,
    test_completion_notification_not_triggered,
    test_assistant_untouched,
    test_attribution_bl_code,
    test_fp_tool_result_str_mid_content,
    test_fp_user_str_mid_content,
    test_fp_text_block_mid_content,
    test_fp_tool_result_list_mid_content,
    test_wording2_tool_result_str_content,
    test_wording2_fp_mid_content_preserved,
    test_wording2_attribution_bl_code,
    test_wording1_and_wording2_same_msg_line,
)
from proxy_176_bg_launch_ack_cases_w3 import (
    test_wording3_tool_result_str_content,
    test_wording3_fp_mid_content_preserved,
    test_wording3_attribution_bl_code,
    test_wording3_message_differs_and_mentions_timeout,
    test_wording3_main_vs_worker,
    test_wording3_ops_path_present,
    test_full_replace_span_is_one_contiguous_block,
    test_wording_main_vs_worker,
)

# ORCHESTRATOR

def proxy_176_bg_launch_ack_tests_workflow():
    test_tool_result_str_content()
    test_text_block_content()
    test_str_message_content()
    test_tool_result_list_content()
    test_non_matching_tool_result_untouched()
    test_completion_notification_not_triggered()
    test_assistant_untouched()
    test_attribution_bl_code()
    test_fp_tool_result_str_mid_content()
    test_fp_user_str_mid_content()
    test_fp_text_block_mid_content()
    test_fp_tool_result_list_mid_content()
    test_wording2_tool_result_str_content()
    test_wording2_fp_mid_content_preserved()
    test_wording2_attribution_bl_code()
    test_wording1_and_wording2_same_msg_line()
    test_wording3_tool_result_str_content()
    test_wording3_fp_mid_content_preserved()
    test_wording3_attribution_bl_code()
    test_wording3_message_differs_and_mentions_timeout()
    test_wording3_main_vs_worker()
    test_wording3_ops_path_present()
    test_full_replace_span_is_one_contiguous_block()
    test_wording_main_vs_worker()
    print("Done.")


if __name__ == "__main__":
    proxy_176_bg_launch_ack_tests_workflow()
