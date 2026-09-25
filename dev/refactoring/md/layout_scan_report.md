# layout_scan report 2026-09-25

files scanned: 413
files with violations: 121
violations: 324

- L1-no-marker: 6
- L5-orchestrator-logic: 287
- L6-guard-not-single-call: 31

## Findings

dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py:54 L5-orchestrator-logic For
dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py:60 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:43 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:45 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:56 L5-orchestrator-logic GeneratorExp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:57 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:59 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:62 L5-orchestrator-logic Compare
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:303 L6-guard-not-single-call guard body is not one statement
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:28 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:30 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:40 L5-orchestrator-logic GeneratorExp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:41 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:43 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:46 L5-orchestrator-logic Compare
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:205 L6-guard-not-single-call guard body is not one statement
dev/cache/extract_bash_file_mods.py:23 L5-orchestrator-logic For
dev/cc_injection_inventory/cc_injection_inventory.py:50 L5-orchestrator-logic For
dev/ccwrap/missing_project_value_check.py:13 L5-orchestrator-logic BoolOp
dev/ccwrap/missing_project_value_check.py:14 L5-orchestrator-logic BinOp
dev/ccwrap/missing_project_value_check.py:15 L5-orchestrator-logic IfExp
dev/click_ui/p1_worker_selection_click_probe.py:30 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:32 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:39 L5-orchestrator-logic GeneratorExp
dev/click_ui/p1_worker_selection_click_probe.py:40 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:42 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:45 L5-orchestrator-logic Compare
dev/click_ui/p1_worker_selection_click_probe.py:260 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p2_copy_click_probe.py:29 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:31 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:38 L5-orchestrator-logic GeneratorExp
dev/click_ui/p2_copy_click_probe.py:39 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:41 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:44 L5-orchestrator-logic Compare
dev/click_ui/p2_copy_click_probe.py:223 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p3_button_click_probe.py:26 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:28 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:33 L5-orchestrator-logic GeneratorExp
dev/click_ui/p3_button_click_probe.py:34 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:36 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:39 L5-orchestrator-logic Compare
dev/click_ui/p3_button_click_probe.py:218 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p4_gpu_news_button_probe.py:24 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:26 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:34 L5-orchestrator-logic GeneratorExp
dev/click_ui/p4_gpu_news_button_probe.py:35 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:37 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:40 L5-orchestrator-logic Compare
dev/click_ui/p4_gpu_news_button_probe.py:271 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p5_proxy_message_copy_click_probe.py:37 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:39 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:57 L5-orchestrator-logic GeneratorExp
dev/click_ui/p5_proxy_message_copy_click_probe.py:58 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:60 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:63 L5-orchestrator-logic Compare
dev/click_ui/p5_proxy_message_copy_click_probe.py:87 L6-guard-not-single-call guard body is not one statement
dev/coteditor/07_space_jump_probe.py:31 L5-orchestrator-logic BinOp
dev/coteditor/07_space_jump_probe.py:42 L5-orchestrator-logic FunctionDef
dev/coteditor/07_space_jump_probe.py:49 L5-orchestrator-logic Try
dev/cursor_edges/probe.py:19 L5-orchestrator-logic BoolOp
dev/cursor_edges/probe.py:25 L5-orchestrator-logic Lambda
dev/cursor_edges/probe.py:38 L5-orchestrator-logic BinOp
dev/desktop_allocation/05_window_detection_probe.py:27 L5-orchestrator-logic For
dev/display/jsonl_exploration/01_map_message_types.py:1 L1-no-marker module has code but no section marker
dev/display/jsonl_exploration/02_map_content_blocks.py:1 L1-no-marker module has code but no section marker
dev/display/jsonl_exploration/03_scan_instructions.py:1 L1-no-marker module has code but no section marker
dev/display/scan_jsonl_rules.py:1 L1-no-marker module has code but no section marker
dev/display/screenshot_panes.py:1 L1-no-marker module has code but no section marker
dev/dual_log_cli/probe_sys_tool_original_chars.py:23 L5-orchestrator-logic GeneratorExp
dev/dual_log_cli/probe_sys_tool_original_chars.py:25 L5-orchestrator-logic BinOp
dev/dual_log_cli/probe_sys_tool_original_chars.py:37 L5-orchestrator-logic AugAssign
dev/dual_log_cli/probe_sys_tool_original_chars.py:38 L5-orchestrator-logic AugAssign
dev/dual_log_cli/probe_sys_tool_original_chars.py:39 L5-orchestrator-logic AugAssign
dev/dual_log_cli/probe_sys_tool_original_chars.py:40 L5-orchestrator-logic AugAssign
dev/dual_log_cli/probe_sys_tool_original_chars.py:41 L5-orchestrator-logic BinOp
dev/dual_log_cli/tests/strand_abort_probe.py:22 L5-orchestrator-logic ListComp
dev/gpu_pane/render_byte_identity.py:22 L5-orchestrator-logic Lambda
dev/gpu_pane/render_byte_identity.py:23 L5-orchestrator-logic Try
dev/hook_smoke/probe_bg_task_live.py:23 L5-orchestrator-logic BinOp
dev/hook_smoke/probe_bg_task_live.py:24 L5-orchestrator-logic BinOp
dev/hook_smoke/probe_bg_task_live.py:25 L5-orchestrator-logic IfExp
dev/hook_smoke/probe_bg_task_live.py:185 L6-guard-not-single-call guard body is not one statement
dev/hook_smoke/probe_replay_cli_chained.py:29 L5-orchestrator-logic DictComp
dev/hook_smoke/probe_replay_cli_chained.py:30 L5-orchestrator-logic For
dev/hook_smoke/probe_replay_cli_chained.py:35 L5-orchestrator-logic GeneratorExp
dev/hook_smoke/probe_replay_cli_chained.py:36 L5-orchestrator-logic GeneratorExp
dev/hook_smoke/probe_replay_cli_chained.py:38 L5-orchestrator-logic For
dev/hook_smoke/verify_bg_task_detection_live.py:24 L5-orchestrator-logic BinOp
dev/hook_smoke/verify_bg_task_detection_live.py:25 L5-orchestrator-logic IfExp
dev/hotkey_latency/analyze_latency.py:26 L5-orchestrator-logic IfExp
dev/hotkey_latency/analyze_latency.py:31 L5-orchestrator-logic BinOp
dev/jsonl/test_jsonl_reader.py:20 L5-orchestrator-logic With
dev/jsonl/test_jsonl_reader.py:22 L5-orchestrator-logic For
dev/jsonl/test_jsonl_reader.py:24 L5-orchestrator-logic IfExp
dev/menubar/discover_byte_identity.py:24 L5-orchestrator-logic ListComp
dev/menubar/model_controller_byte_identity.py:30 L5-orchestrator-logic Try
dev/menubar/p5_run_all.py:14 L5-orchestrator-logic With
dev/menubar/panel_manager_byte_identity.py:23 L5-orchestrator-logic Try
dev/menubar_nspanel/menubar_debug.py:22 L5-orchestrator-logic Try
dev/menubar_nspanel/menubar_debug.py:52 L6-guard-not-single-call guard body is not one statement
dev/model_selector/verify_four_tab_ring.py:32 L5-orchestrator-logic With
dev/model_selector/verify_four_tab_ring.py:41 L5-orchestrator-logic BinOp
dev/model_selector/verify_hook17_removal.py:30 L5-orchestrator-logic BinOp
dev/model_selector/verify_hook_writer_split.py:19 L5-orchestrator-logic With
dev/model_selector/verify_hook_writer_split.py:45 L5-orchestrator-logic BinOp
dev/monitor_lifecycle/probe_monitor_load.py:16 L5-orchestrator-logic Lambda
dev/monitor_root/test_monitor_root.py:26 L5-orchestrator-logic With
dev/native-model-start/p2_model_params_probe.py:51 L5-orchestrator-logic BinOp
dev/native-model-start/p3_cache_breakpoints_probe.py:35 L5-orchestrator-logic Import
dev/native-model-start/p3_cache_breakpoints_probe.py:36 L5-orchestrator-logic For
dev/native-model-start/p4_dual_log_integrity_probe.py:40 L5-orchestrator-logic For
dev/native-model-start/p4_dual_log_integrity_probe.py:62 L5-orchestrator-logic BinOp
dev/nsgridview_migration/probe.py:43 L5-orchestrator-logic Lambda
dev/nsgridview_migration/probe.py:54 L5-orchestrator-logic BinOp
dev/nsgridview_migration/probe.py:55 L5-orchestrator-logic BinOp
dev/pane_flicker/bench_hover_render.py:23 L5-orchestrator-logic Try
dev/pane_flicker/m1_frame_e2e_test.py:29 L5-orchestrator-logic With
dev/pane_flicker/m1_frame_e2e_test.py:35 L5-orchestrator-logic IfExp
dev/pane_flicker/m1_strand_abort_test.py:17 L5-orchestrator-logic With
dev/pane_flicker/m2_byte_identity_test.py:24 L5-orchestrator-logic With
dev/pane_flicker/m2_byte_identity_test.py:30 L5-orchestrator-logic IfExp
dev/pane_flicker/m2_state_sequence_driver.py:25 L5-orchestrator-logic Lambda
dev/pane_flicker/m2_state_sequence_driver.py:29 L5-orchestrator-logic With
dev/pane_flicker/observe_timestamp_order.py:20 L5-orchestrator-logic AugAssign
dev/pane_flicker/observe_timestamp_order.py:21 L5-orchestrator-logic AugAssign
dev/pane_flicker/run_scenarios.py:21 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:23 L5-orchestrator-logic With
dev/pane_flicker/run_scenarios.py:25 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:26 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:28 L5-orchestrator-logic BoolOp
dev/pane_flicker/run_scenarios.py:29 L5-orchestrator-logic IfExp
dev/pane_flicker/run_scenarios.py:30 L5-orchestrator-logic IfExp
dev/pane_flicker/scenario_run.py:20 L5-orchestrator-logic Try
dev/pane_search/p1_full_sweep_cost_probe.py:28 L5-orchestrator-logic Delete
dev/pane_search/p1_full_sweep_cost_probe.py:32 L5-orchestrator-logic Delete
dev/pane_search/p1_full_sweep_cost_probe.py:43 L5-orchestrator-logic BinOp
dev/pane_search/p1_full_sweep_cost_probe.py:49 L6-guard-not-single-call guard body is not one statement
dev/panes/test_display_tripwires.py:20 L5-orchestrator-logic With
dev/panes/test_display_tripwires.py:22 L5-orchestrator-logic For
dev/panes/test_display_tripwires.py:24 L5-orchestrator-logic IfExp
dev/proxy/addon_hook_byte_identity.py:28 L5-orchestrator-logic With
dev/proxy/pipeline_byte_identity.py:25 L5-orchestrator-logic For
dev/proxy/replay_env_context_strip.py:40 L5-orchestrator-logic For
dev/proxy/replay_env_context_strip.py:192 L6-guard-not-single-call guard body is not one statement
dev/proxy/scan_sr_catalog.py:50 L5-orchestrator-logic GeneratorExp
dev/proxy/scan_sr_catalog.py:51 L5-orchestrator-logic GeneratorExp
dev/proxy/test_live_copy_bootstrap.py:25 L5-orchestrator-logic BinOp
dev/proxy/test_live_copy_bootstrap.py:28 L5-orchestrator-logic GeneratorExp
dev/proxy/test_live_copy_bootstrap.py:29 L5-orchestrator-logic With
dev/proxy/test_proxy_config_trace.py:19 L5-orchestrator-logic BinOp
dev/proxy/test_proxy_config_trace.py:22 L5-orchestrator-logic GeneratorExp
dev/proxy/test_proxy_config_trace.py:23 L5-orchestrator-logic With
dev/proxy/test_proxy_env_and_family.py:19 L5-orchestrator-logic BinOp
dev/proxy/test_proxy_env_and_family.py:22 L5-orchestrator-logic GeneratorExp
dev/proxy/test_proxy_env_and_family.py:23 L5-orchestrator-logic With
dev/proxy/test_proxy_error_log.py:19 L5-orchestrator-logic BinOp
dev/proxy/test_proxy_error_log.py:22 L5-orchestrator-logic GeneratorExp
dev/proxy/test_proxy_error_log.py:23 L5-orchestrator-logic With
dev/proxy/test_proxy_start_fallbacks.py:20 L5-orchestrator-logic BinOp
dev/proxy/test_proxy_start_fallbacks.py:22 L5-orchestrator-logic Try
dev/proxy/verify_proxy_start_equivalence.py:33 L5-orchestrator-logic BinOp
dev/proxy/verify_proxy_start_equivalence.py:36 L5-orchestrator-logic Try
dev/proxy_analysis/01_session_summary.py:243 L6-guard-not-single-call guard body is not one statement
dev/proxy_display/test_forwarded_tripwires.py:19 L5-orchestrator-logic With
dev/proxy_display/test_forwarded_tripwires.py:21 L5-orchestrator-logic For
dev/proxy_display/test_forwarded_tripwires.py:23 L5-orchestrator-logic IfExp
dev/proxy_display/test_pd10_lazy_messages.py:20 L5-orchestrator-logic With
dev/proxy_display/test_pd10_lazy_messages.py:22 L5-orchestrator-logic For
dev/proxy_display/test_pd10_lazy_messages.py:24 L5-orchestrator-logic IfExp
dev/proxy_display/test_session_marker_states.py:19 L5-orchestrator-logic With
dev/proxy_display/test_session_marker_states.py:21 L5-orchestrator-logic For
dev/proxy_display/test_session_marker_states.py:23 L5-orchestrator-logic IfExp
dev/proxy_dual_log/attribution_coverage/attribution_coverage.py:39 L5-orchestrator-logic BinOp
dev/proxy_dual_log/diff_strip_inject.py:237 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:20 L5-orchestrator-logic FunctionDef
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:33 L5-orchestrator-logic BinOp
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:34 L5-orchestrator-logic With
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:27 L5-orchestrator-logic FunctionDef
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:32 L5-orchestrator-logic ListComp
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:35 L5-orchestrator-logic For
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:43 L5-orchestrator-logic BinOp
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:44 L5-orchestrator-logic With
dev/proxy_dual_log/main_log_elimination_probe/main_log_elimination_probe.py:43 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:34 L5-orchestrator-logic BinOp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:35 L5-orchestrator-logic BinOp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:45 L5-orchestrator-logic ListComp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:50 L5-orchestrator-logic BinOp
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:19 L5-orchestrator-logic ImportFrom
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:25 L5-orchestrator-logic BinOp
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:28 L5-orchestrator-logic FunctionDef
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:37 L5-orchestrator-logic With
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:34 L5-orchestrator-logic Compare
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:38 L5-orchestrator-logic BinOp
dev/proxy_dual_log/tt_delta_skip_replay.py:51 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:270 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/verify_delta.py:42 L5-orchestrator-logic ListComp
dev/proxy_dual_log/verify_delta.py:43 L5-orchestrator-logic IfExp
dev/proxy_dual_log/verify_delta.py:263 L6-guard-not-single-call guard body is not one statement
dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py:29 L5-orchestrator-logic For
dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py:35 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:45 L5-orchestrator-logic For
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:49 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:52 L5-orchestrator-logic For
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:54 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:55 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:30 L5-orchestrator-logic BoolOp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:38 L5-orchestrator-logic For
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:53 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:54 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:56 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:57 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p7_blocklist_258_probe.py:27 L5-orchestrator-logic AugAssign
dev/proxy_instrumentation/render_recorded_request.py:24 L5-orchestrator-logic ImportFrom
dev/proxy_instrumentation/render_recorded_request.py:32 L5-orchestrator-logic Compare
dev/proxy_instrumentation/render_recorded_request.py:34 L5-orchestrator-logic For
dev/proxy_instrumentation/render_recorded_request.py:37 L5-orchestrator-logic For
dev/proxy_instrumentation/render_recorded_request.py:40 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/render_recorded_request.py:45 L5-orchestrator-logic Compare
dev/proxy_instrumentation/render_recorded_request.py:47 L5-orchestrator-logic For
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:29 L5-orchestrator-logic For
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:63 L5-orchestrator-logic For
dev/refactoring/strand_runner.py:23 L5-orchestrator-logic IfExp
dev/refactoring/strand_runner_selftest.py:43 L5-orchestrator-logic With
dev/session_analysis/04_cache_validation.py:40 L5-orchestrator-logic BinOp
dev/session_analysis/04_cache_validation.py:46 L5-orchestrator-logic IfExp
dev/session_analysis/05_req_breakdown.py:20 L5-orchestrator-logic IfExp
dev/session_analysis/05_req_breakdown.py:39 L5-orchestrator-logic BinOp
dev/session_analysis/07_quartet_prefix_diff.py:23 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:30 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:31 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:32 L5-orchestrator-logic BinOp
dev/session_analysis/07_quartet_prefix_diff.py:33 L5-orchestrator-logic ListComp
dev/session_analysis/07_quartet_prefix_diff.py:40 L5-orchestrator-logic ListComp
dev/session_analysis/07_quartet_prefix_diff.py:49 L5-orchestrator-logic BinOp
dev/session_launcher/p2_panel_snapshot.py:30 L5-orchestrator-logic BinOp
dev/session_launcher/s1_switch_probe.py:30 L5-orchestrator-logic BinOp
dev/session_launcher/s1_switch_probe.py:35 L5-orchestrator-logic For
dev/session_launcher/s2_ghostty_window_probe.py:33 L5-orchestrator-logic BinOp
dev/session_launcher/s2_ghostty_window_probe.py:37 L5-orchestrator-logic For
dev/session_launcher/t1_autojump_removal.py:33 L5-orchestrator-logic ListComp
dev/session_launcher/t1_autojump_removal.py:37 L5-orchestrator-logic GeneratorExp
dev/session_launcher/t2_launch_tab.py:45 L5-orchestrator-logic With
dev/session_launcher/t2_launch_tab.py:51 L5-orchestrator-logic GeneratorExp
dev/session_launcher/t3_tab_click.py:37 L5-orchestrator-logic With
dev/session_launcher/t3_tab_click.py:43 L5-orchestrator-logic GeneratorExp
dev/setup_py2app/exit_on_failure_checks.py:19 L5-orchestrator-logic BinOp
dev/setup_py2app/exit_on_failure_checks.py:20 L5-orchestrator-logic For
dev/setup_py2app/exit_on_failure_checks.py:22 L5-orchestrator-logic ListComp
dev/setup_py2app/exit_on_failure_checks.py:23 L5-orchestrator-logic BinOp
dev/setup_py2app/exit_on_failure_checks.py:24 L5-orchestrator-logic IfExp
dev/skill_picker/p1_real_discovery.py:25 L5-orchestrator-logic ListComp
dev/skill_picker/p1_real_discovery.py:26 L5-orchestrator-logic IfExp
dev/skill_picker/t1_skill_picker.py:46 L5-orchestrator-logic With
dev/skill_picker/t1_skill_picker.py:50 L5-orchestrator-logic BinOp
dev/skill_picker/t1_skill_picker.py:54 L5-orchestrator-logic GeneratorExp
dev/sleep_pattern_analysis/analyze.py:19 L5-orchestrator-logic IfExp
dev/thinking/render_brain_badge.py:106 L6-guard-not-single-call guard body is not one statement
dev/thinking/render_thinking_expander.py:239 L6-guard-not-single-call guard body is not one statement
dev/timer-loop/p1_scan_bg_completion_wordings.py:20 L5-orchestrator-logic IfExp
dev/timer-loop/p1_scan_bg_completion_wordings.py:21 L5-orchestrator-logic GeneratorExp
dev/timer-loop/p1_scan_bg_completion_wordings.py:32 L5-orchestrator-logic For
dev/timer-loop/p1_scan_bg_completion_wordings.py:41 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:27 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:29 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:37 L5-orchestrator-logic GeneratorExp
dev/timer-loop/p3_project_scope_incident_probe.py:38 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:40 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:42 L5-orchestrator-logic Compare
dev/timer-loop/p3_project_scope_incident_probe.py:213 L6-guard-not-single-call guard body is not one statement
dev/tmux_launcher/fallback_tripwire_checks.py:30 L5-orchestrator-logic Try
dev/tmux_launcher/fallback_tripwire_checks.py:38 L5-orchestrator-logic ListComp
dev/tmux_launcher/fallback_tripwire_checks.py:39 L5-orchestrator-logic For
dev/tmux_launcher/fallback_tripwire_checks.py:41 L5-orchestrator-logic BinOp
dev/tmux_launcher/fallback_tripwire_checks.py:42 L5-orchestrator-logic IfExp
dev/tool_injection/01_extract_schemas.py:61 L5-orchestrator-logic For
dev/tool_injection/01_extract_schemas.py:72 L5-orchestrator-logic For
dev/tool_injection/01_extract_schemas.py:76 L5-orchestrator-logic For
dev/tool_use_analysis/cc_injection_audit.py:28 L5-orchestrator-logic For
dev/tool_use_analysis/cc_injection_audit.py:275 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_long_calls.py:26 L5-orchestrator-logic Lambda
dev/tool_use_analysis/extract_long_calls.py:33 L5-orchestrator-logic ListComp
dev/tool_use_analysis/extract_long_calls.py:36 L5-orchestrator-logic ListComp
dev/tool_use_analysis/extract_long_calls.py:37 L5-orchestrator-logic Lambda
dev/tool_use_analysis/extract_long_calls.py:73 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_patterns.py:20 L5-orchestrator-logic For
dev/tool_use_analysis/extract_patterns.py:66 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_transcript.py:19 L5-orchestrator-logic For
dev/tool_use_analysis/extract_transcript.py:33 L5-orchestrator-logic BinOp
dev/tool_use_analysis/extract_transcript.py:35 L5-orchestrator-logic With
dev/tool_use_analysis/extract_transcript.py:157 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_zeros.py:24 L5-orchestrator-logic For
dev/tool_use_analysis/extract_zeros.py:340 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/rag_query_audit.py:34 L5-orchestrator-logic For
dev/tool_use_analysis/rag_query_audit.py:311 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/rag_truncation_audit.py:19 L5-orchestrator-logic For
dev/tool_use_analysis/rag_truncation_audit.py:46 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/rs_truncation_preserve_replay.py:90 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/sr_bypass_audit.py:35 L5-orchestrator-logic For
dev/tool_use_analysis/sr_bypass_audit.py:216 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/sr_session_audit.py:37 L5-orchestrator-logic BoolOp
dev/tool_use_analysis/sr_session_audit.py:39 L5-orchestrator-logic DictComp
dev/tool_use_analysis/sr_session_audit.py:43 L5-orchestrator-logic For
dev/tool_use_analysis/sr_session_audit.py:68 L5-orchestrator-logic BinOp
dev/tool_use_analysis/strip_audit.py:26 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:28 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:29 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:30 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:68 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/tag_presence_audit.py:70 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/waste_repetition.py:284 L6-guard-not-single-call guard body is not one statement
dev/verbosity/extract_turns.py:1 L1-no-marker module has code but no section marker
dev/worker_status_probes/probe_a.py:16 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_a.py:17 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_b.py:24 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_b.py:25 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_c.py:21 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_c.py:22 L5-orchestrator-logic Lambda
dev/worker_status_probes/run_all.py:32 L5-orchestrator-logic BinOp
dev/worker_status_probes/run_all.py:38 L5-orchestrator-logic Lambda
dev/worker_status_probes/run_all.py:39 L5-orchestrator-logic Lambda
dev/worker_status_probes/run_all.py:43 L5-orchestrator-logic For
dev/workers/test_worker_probes.py:22 L5-orchestrator-logic With
dev/workers/test_worker_probes.py:24 L5-orchestrator-logic For
dev/workers/test_worker_probes.py:26 L5-orchestrator-logic IfExp
