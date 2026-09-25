#!/usr/bin/env python3

# INFRASTRUCTURE
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.live_log_isolation import isolate_monitor_root

_ROOT_SANDBOX = isolate_monitor_root("test_strip_fix_")

from dev.refactoring.strand_runner import strand_workflow
from test_strip_fix_cases_templates import (
    t01_task_tools_nag_real_text_block, t02_task_tools_nag_fp_code_literal, t03_task_tools_nag_tool_result_preserved,
    t04_pyright_real, t05_pyright_fp, t06_pyright_tool_result_nested_preserved,
    t07_deferred_tools_real, t08_deferred_tools_fp, t09_deferred_tools_tool_result_preserved,
    t10_user_interrupt_partial_body_preserved, t11_user_interrupt_fp, t12_user_interrupt_tool_result_preserved,
    t13_system_notification_real, t14_system_notification_fp, t15_system_notification_tool_result_preserved,
    t16_file_modified_real, t17_file_modified_fp, t18_file_modified_tool_result_preserved,
    t19_claudemd_real, t20_claudemd_fp, t21_claudemd_tool_result_preserved,
    t22_date_changed_real, t23_date_changed_fp, t24_date_changed_tool_result_preserved,
    t25_shape_plain_string, t26_shape_list_text, t27_shape_tool_result_str_now_preserved, t28_shape_tool_result_list_now_preserved,
    t29_plan_mode_returns_none_when_empty, t30_plan_mode_preserves_other_content,
    t31_find_sr_blocks_tool_result_finds_none, t32_find_sr_blocks_top_level_real_found,
    t33_content_contains_tool_result_str, t34_content_contains_text_block,
    t35_final_sr_pass_tool_result_str_identity_preserved, t36_final_sr_pass_tool_result_list_identity_preserved,
    t37_occurrence8_fenced_env_context_in_tool_result_preserved,
    t38_top_level_task_tools_nag_still_stripped_via_first_pass, t39_top_level_date_changed_still_stripped_via_final_sr_pass,
)
from test_strip_fix_cases_env_context import (
    t40_env_context_may_2026_form_stripped, t41_env_context_cc258_form_stripped,
    t42_claudemd_context_block_preserved, t43_env_context_different_email_preserved,
    t44_bundled_claudemd_and_env_context_preserved,
    t45_env_context_gitstatus_corpus_block_main_clean_stripped,
    t46_env_context_gitstatus_corpus_block_integration_branch_stripped,
    t47_env_context_gitstatus_dirty_status_stripped,
    t48_env_context_gitstatus_head_branch_stripped,
    t49_bundled_claudemd_and_gitstatus_preserved,
    t50_env_context_gitstatus_issue86891_shape_stripped,
    t51_env_context_gitstatus_issue43250_shape_stripped,
)
from test_strip_fix_cases_git_attribution import (
    ga01_observed_block_stripped_env_stripped_task_untouched, ga02_model_name_not_matched,
    ga03_quoted_copy_in_tool_result_preserved, ga04_full_pipeline_main_and_worker_context,
    ga05_mid_text_mention_preserved,
)
from test_strip_fix_cases_wakeup import (
    w01_tn_in_tool_result_str, w02_tn_in_tool_result_list, w03_bgk_in_tool_result_str,
    w04_genuine_tn_completed_plain_string, w05_genuine_tn_failed_plain_string,
    w06_genuine_bgk_plain_string,
    w07_sn_notice_genuine_plain_string, w08_sn_notice_text_block_index_one,
    w09_sn_notice_tool_result_untouched, w10_sn_notice_mid_content_untouched,
    w11_sn_notice_role_system_untouched,
    w12_role_system_tn_completed_full_pipeline, w13_role_system_tn_failed_with_output_file,
    w14_role_system_noise_still_nuked_through_full_chain,
    w30_role_system_mid_turn_user_msg_preserved_whole,
)
from test_strip_fix_cases_launch_ack_interrupt import (
    w15_launch_ack_id_and_path_full, w16_launch_ack_missing_id_omits_id_line,
    w17_launch_ack_missing_path_omits_output_line, w18_launch_ack_real_corpus_body_exact,
    w19_tn_real_corpus_body_exact, w20_tn_missing_task_id_omits_id_line,
    w21_tn_missing_output_file_omits_output_line, w22_tn_no_id_no_output_reduces_to_bare_wakeup,
    w23_launch_ack_wording2_real_body_exact, w24_launch_ack_wording2_trailing_content_not_swallowed_into_path,
    w34_launch_ack_wording3_real_corpus_body_exact,
    w25_interrupt_marker_real_shape_neighbors_intact, w26_interrupt_marker_four_shapes,
    w26b_interrupt_marker_tool_use_wording,
    w27_interrupt_marker_embedded_in_longer_text_untouched, w28_interrupt_marker_pass_role_gate_and_mod,
    w29_interrupt_marker_pass_tool_use_wording,
)
from test_strip_fix_cases_wrapped_tn import (
    w31_sr_wrapped_tn_full_chain_yields_bare_wakeup, w32_bare_role_system_tn_full_chain_unchanged,
    w33_unwrapped_user_tn_full_chain_unchanged,
)
from test_strip_fix_cases_badge import (
    tt01_total_tokens_still_written_with_spans, tt02_total_tokens_badge_false_but_overlay_intact,
    tt03_other_nukes_badge_strip_and_inject, tt04_real_injection_still_badges,
    tt05_marker_with_surrounding_content_still_badges, tt06_anchoring_near_misses_still_badge,
    tt07_mixed_request_still_badges, tt08_other_sections_unaffected,
    tt09_rendered_header_badge_words,
)
from test_strip_fix_cases_badge_nudge import (
    tt10_nudge_prefixed_tag_badges_neither_word, tt11_nudge_mixed_with_real_content_still_badges,
    tt12_two_trailing_messages_in_one_delta_stays_quiet, tt13_lag_classifier_widens_for_nudge_shape,
    tt14_rendered_header_badge_words_for_nudge_class,
)
from test_strip_fix_cases_pasted_content import (
    pc01_real_whole_message_wrap_stripped, pc02_real_wrap_then_trailing_text_same_message,
    pc03_real_leading_text_then_wrap, pc04_real_short_leading_text_then_wrap,
    pc05_real_fenced_quote_in_assistant_role_preserved_whole,
    pc06_real_tool_result_wellformed_pair_preserved, pc07_real_tool_result_malformed_tag_mention_preserved,
    pc08_real_tool_result_bare_mention_preserved, pc09_real_tool_result_word_mention_preserved,
    pc10_pass_role_gate_and_mod_and_ops, pc11_full_pipeline_attribution_via_strip_vocab,
)

# ORCHESTRATOR

def run_test_strip_fix_workflow() -> int:
    return strand_workflow(globals(), __file__, _case_names(), title='test_strip_fix')


# FUNCTIONS

def _case_names() -> list:
    groups = [_seq_templates, _seq_env_context, _seq_git_attribution, _seq_wakeup,
              _seq_launch_ack_interrupt, _seq_wrapped_tn, _seq_badge, _seq_pasted_content]
    return sorted(fn.__name__ for group in groups for fn in group())


def _seq_templates() -> list:
    return [
        t01_task_tools_nag_real_text_block, t02_task_tools_nag_fp_code_literal, t03_task_tools_nag_tool_result_preserved,
        t04_pyright_real, t05_pyright_fp, t06_pyright_tool_result_nested_preserved,
        t07_deferred_tools_real, t08_deferred_tools_fp, t09_deferred_tools_tool_result_preserved,
        t10_user_interrupt_partial_body_preserved, t11_user_interrupt_fp, t12_user_interrupt_tool_result_preserved,
        t13_system_notification_real, t14_system_notification_fp, t15_system_notification_tool_result_preserved,
        t16_file_modified_real, t17_file_modified_fp, t18_file_modified_tool_result_preserved,
        t19_claudemd_real, t20_claudemd_fp, t21_claudemd_tool_result_preserved,
        t22_date_changed_real, t23_date_changed_fp, t24_date_changed_tool_result_preserved,
        t25_shape_plain_string, t26_shape_list_text, t27_shape_tool_result_str_now_preserved, t28_shape_tool_result_list_now_preserved,
        t29_plan_mode_returns_none_when_empty, t30_plan_mode_preserves_other_content,
        t31_find_sr_blocks_tool_result_finds_none, t32_find_sr_blocks_top_level_real_found,
        t33_content_contains_tool_result_str, t34_content_contains_text_block,
        t35_final_sr_pass_tool_result_str_identity_preserved, t36_final_sr_pass_tool_result_list_identity_preserved,
        t37_occurrence8_fenced_env_context_in_tool_result_preserved,
        t38_top_level_task_tools_nag_still_stripped_via_first_pass, t39_top_level_date_changed_still_stripped_via_final_sr_pass,
    ]


def _seq_env_context() -> list:
    return [
        t40_env_context_may_2026_form_stripped, t41_env_context_cc258_form_stripped,
        t42_claudemd_context_block_preserved, t43_env_context_different_email_preserved,
        t44_bundled_claudemd_and_env_context_preserved,
        t45_env_context_gitstatus_corpus_block_main_clean_stripped,
        t46_env_context_gitstatus_corpus_block_integration_branch_stripped,
        t47_env_context_gitstatus_dirty_status_stripped,
        t48_env_context_gitstatus_head_branch_stripped,
        t49_bundled_claudemd_and_gitstatus_preserved,
        t50_env_context_gitstatus_issue86891_shape_stripped,
        t51_env_context_gitstatus_issue43250_shape_stripped,
    ]


def _seq_git_attribution() -> list:
    return [
        ga01_observed_block_stripped_env_stripped_task_untouched, ga02_model_name_not_matched,
        ga03_quoted_copy_in_tool_result_preserved, ga04_full_pipeline_main_and_worker_context,
        ga05_mid_text_mention_preserved,
    ]


def _seq_wakeup() -> list:
    return [
        w01_tn_in_tool_result_str, w02_tn_in_tool_result_list, w03_bgk_in_tool_result_str,
        w04_genuine_tn_completed_plain_string, w05_genuine_tn_failed_plain_string,
        w06_genuine_bgk_plain_string,
        w07_sn_notice_genuine_plain_string, w08_sn_notice_text_block_index_one,
        w09_sn_notice_tool_result_untouched, w10_sn_notice_mid_content_untouched,
        w11_sn_notice_role_system_untouched,
        w12_role_system_tn_completed_full_pipeline, w13_role_system_tn_failed_with_output_file,
        w14_role_system_noise_still_nuked_through_full_chain,
    ]


def _seq_launch_ack_interrupt() -> list:
    return [
        w15_launch_ack_id_and_path_full, w16_launch_ack_missing_id_omits_id_line,
        w17_launch_ack_missing_path_omits_output_line, w18_launch_ack_real_corpus_body_exact,
        w19_tn_real_corpus_body_exact, w20_tn_missing_task_id_omits_id_line,
        w21_tn_missing_output_file_omits_output_line, w22_tn_no_id_no_output_reduces_to_bare_wakeup,
        w23_launch_ack_wording2_real_body_exact, w24_launch_ack_wording2_trailing_content_not_swallowed_into_path,
        w34_launch_ack_wording3_real_corpus_body_exact,
        w25_interrupt_marker_real_shape_neighbors_intact, w26_interrupt_marker_four_shapes,
        w26b_interrupt_marker_tool_use_wording,
        w27_interrupt_marker_embedded_in_longer_text_untouched, w28_interrupt_marker_pass_role_gate_and_mod,
        w29_interrupt_marker_pass_tool_use_wording,
        w30_role_system_mid_turn_user_msg_preserved_whole,
    ]


def _seq_wrapped_tn() -> list:
    return [
        w31_sr_wrapped_tn_full_chain_yields_bare_wakeup, w32_bare_role_system_tn_full_chain_unchanged,
        w33_unwrapped_user_tn_full_chain_unchanged,
    ]


def _seq_badge() -> list:
    return [
        tt01_total_tokens_still_written_with_spans, tt02_total_tokens_badge_false_but_overlay_intact,
        tt03_other_nukes_badge_strip_and_inject, tt04_real_injection_still_badges,
        tt05_marker_with_surrounding_content_still_badges, tt06_anchoring_near_misses_still_badge,
        tt07_mixed_request_still_badges, tt08_other_sections_unaffected,
        tt09_rendered_header_badge_words,
        tt10_nudge_prefixed_tag_badges_neither_word, tt11_nudge_mixed_with_real_content_still_badges,
        tt12_two_trailing_messages_in_one_delta_stays_quiet, tt13_lag_classifier_widens_for_nudge_shape,
        tt14_rendered_header_badge_words_for_nudge_class,
    ]


def _seq_pasted_content() -> list:
    return [
        pc01_real_whole_message_wrap_stripped, pc02_real_wrap_then_trailing_text_same_message,
        pc03_real_leading_text_then_wrap, pc04_real_short_leading_text_then_wrap,
        pc05_real_fenced_quote_in_assistant_role_preserved_whole,
        pc06_real_tool_result_wellformed_pair_preserved, pc07_real_tool_result_malformed_tag_mention_preserved,
        pc08_real_tool_result_bare_mention_preserved, pc09_real_tool_result_word_mention_preserved,
        pc10_pass_role_gate_and_mod_and_ops, pc11_full_pipeline_attribution_via_strip_vocab,
    ]


if __name__ == '__main__':
    sys.exit(run_test_strip_fix_workflow())
