# layout_scan report 2026-09-25

files scanned: 412
files with violations: 187
violations: 604

- L1-no-marker: 6
- L2-marker-order: 25
- L3-functions-content: 21
- L3-infra-content: 62
- L4-orchestrator-not-one-function: 21
- L5-orchestrator-logic: 335
- L6-guard-not-single-call: 33
- L6-module-level-call: 2
- L6-script-without-orchestrator: 3
- L7-stepdown-order: 96

## Findings

dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py:53 L5-orchestrator-logic For
dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py:59 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py:66 L7-stepdown-order _iter_candidate_blocks out of call order
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:29 L3-infra-content FunctionDef
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:260 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:263 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:265 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:276 L5-orchestrator-logic GeneratorExp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:277 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:279 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:282 L5-orchestrator-logic Compare
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:286 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:289 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:298 L5-orchestrator-logic For
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:300 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p2_bg_escape_probe.py:304 L6-guard-not-single-call guard body is not one statement
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:25 L3-infra-content FunctionDef
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:162 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:165 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:167 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:177 L5-orchestrator-logic GeneratorExp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:178 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:180 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:183 L5-orchestrator-logic Compare
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:187 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:190 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:199 L5-orchestrator-logic For
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:201 L5-orchestrator-logic BinOp
dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py:205 L6-guard-not-single-call guard body is not one statement
dev/cache/extract_bash_file_mods.py:23 L5-orchestrator-logic For
dev/cache/extract_bash_file_mods.py:92 L7-stepdown-order _run_output_path out of call order
dev/cc_injection_inventory/cc_injection_inventory.py:50 L5-orchestrator-logic For
dev/cc_injection_inventory/cc_injection_inventory.py:74 L7-stepdown-order _default_log_dir out of call order
dev/ccwrap/missing_project_value_check.py:13 L5-orchestrator-logic BoolOp
dev/ccwrap/missing_project_value_check.py:14 L5-orchestrator-logic BinOp
dev/ccwrap/missing_project_value_check.py:15 L5-orchestrator-logic IfExp
dev/click_ui/p1_worker_selection_click_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/click_ui/p1_worker_selection_click_probe.py:27 L3-infra-content FunctionDef
dev/click_ui/p1_worker_selection_click_probe.py:220 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/click_ui/p1_worker_selection_click_probe.py:223 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:225 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:232 L5-orchestrator-logic GeneratorExp
dev/click_ui/p1_worker_selection_click_probe.py:233 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:235 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:238 L5-orchestrator-logic Compare
dev/click_ui/p1_worker_selection_click_probe.py:242 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:245 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:254 L5-orchestrator-logic For
dev/click_ui/p1_worker_selection_click_probe.py:256 L5-orchestrator-logic BinOp
dev/click_ui/p1_worker_selection_click_probe.py:260 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p2_copy_click_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/click_ui/p2_copy_click_probe.py:26 L3-infra-content FunctionDef
dev/click_ui/p2_copy_click_probe.py:30 L3-infra-content FunctionDef
dev/click_ui/p2_copy_click_probe.py:182 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/click_ui/p2_copy_click_probe.py:185 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:187 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:194 L5-orchestrator-logic GeneratorExp
dev/click_ui/p2_copy_click_probe.py:195 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:197 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:200 L5-orchestrator-logic Compare
dev/click_ui/p2_copy_click_probe.py:204 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:207 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:216 L5-orchestrator-logic For
dev/click_ui/p2_copy_click_probe.py:218 L5-orchestrator-logic BinOp
dev/click_ui/p2_copy_click_probe.py:222 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p3_button_click_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/click_ui/p3_button_click_probe.py:23 L3-infra-content FunctionDef
dev/click_ui/p3_button_click_probe.py:180 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/click_ui/p3_button_click_probe.py:183 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:185 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:190 L5-orchestrator-logic GeneratorExp
dev/click_ui/p3_button_click_probe.py:191 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:193 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:196 L5-orchestrator-logic Compare
dev/click_ui/p3_button_click_probe.py:200 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:203 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:212 L5-orchestrator-logic For
dev/click_ui/p3_button_click_probe.py:214 L5-orchestrator-logic BinOp
dev/click_ui/p3_button_click_probe.py:218 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p4_gpu_news_button_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/click_ui/p4_gpu_news_button_probe.py:21 L3-infra-content FunctionDef
dev/click_ui/p4_gpu_news_button_probe.py:230 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/click_ui/p4_gpu_news_button_probe.py:233 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:235 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:243 L5-orchestrator-logic GeneratorExp
dev/click_ui/p4_gpu_news_button_probe.py:244 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:246 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:249 L5-orchestrator-logic Compare
dev/click_ui/p4_gpu_news_button_probe.py:253 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:256 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:265 L5-orchestrator-logic For
dev/click_ui/p4_gpu_news_button_probe.py:267 L5-orchestrator-logic BinOp
dev/click_ui/p4_gpu_news_button_probe.py:271 L6-guard-not-single-call guard body is not one statement
dev/click_ui/p5_proxy_message_copy_click_probe.py:33 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/click_ui/p5_proxy_message_copy_click_probe.py:36 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:38 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:56 L5-orchestrator-logic GeneratorExp
dev/click_ui/p5_proxy_message_copy_click_probe.py:57 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:59 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:62 L5-orchestrator-logic Compare
dev/click_ui/p5_proxy_message_copy_click_probe.py:66 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:69 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:78 L5-orchestrator-logic For
dev/click_ui/p5_proxy_message_copy_click_probe.py:80 L5-orchestrator-logic BinOp
dev/click_ui/p5_proxy_message_copy_click_probe.py:84 L6-guard-not-single-call guard body is not one statement
dev/click_ui/proxy_copy_probe_shared.py:15 L3-infra-content FunctionDef
dev/click_ui/proxy_copy_probe_shared.py:19 L3-infra-content FunctionDef
dev/constants/split_byte_identity.py:50 L7-stepdown-order _resolve out of call order
dev/coteditor/07_space_jump_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/coteditor/07_space_jump_probe.py:86 L5-orchestrator-logic BinOp
dev/coteditor/07_space_jump_probe.py:97 L5-orchestrator-logic FunctionDef
dev/coteditor/07_space_jump_probe.py:104 L5-orchestrator-logic Try
dev/coteditor/07_space_jump_probe.py:28 L7-stepdown-order _left_button_down out of call order
dev/cursor_edges/probe.py:130 L3-functions-content Expr
dev/cursor_edges/probe.py:19 L5-orchestrator-logic BoolOp
dev/cursor_edges/probe.py:25 L5-orchestrator-logic Lambda
dev/cursor_edges/probe.py:38 L5-orchestrator-logic BinOp
dev/cursor_edges/probe.py:130 L6-module-level-call main()
dev/desktop_allocation/05_window_detection_probe.py:27 L5-orchestrator-logic For
dev/display/A_format_cache_tracker_proof.py:17 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/display/A_format_cache_tracker_proof.py:20 L5-orchestrator-logic ImportFrom
dev/display/jsonl_exploration/01_map_message_types.py:1 L1-no-marker module has code but no section marker
dev/display/jsonl_exploration/02_map_content_blocks.py:1 L1-no-marker module has code but no section marker
dev/display/jsonl_exploration/03_scan_instructions.py:1 L1-no-marker module has code but no section marker
dev/display/scan_jsonl_rules.py:1 L1-no-marker module has code but no section marker
dev/display/screenshot_panes.py:1 L1-no-marker module has code but no section marker
dev/dual_log_cli/probe_sys_tool_original_chars.py:246 L6-script-without-orchestrator 13 functions
dev/dual_log_cli/tests/strand_abort_probe.py:22 L5-orchestrator-logic ListComp
dev/dual_log_cli/tests/test_skip_reporting.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/dual_log_cli/tests/test_skip_reporting.py:29 L7-stepdown-order _strand_cases out of call order
dev/gpu_pane/render_byte_identity.py:22 L5-orchestrator-logic Lambda
dev/gpu_pane/render_byte_identity.py:23 L5-orchestrator-logic Try
dev/gpu_pane/render_byte_identity.py:77 L7-stepdown-order _strip_ansi_for_match out of call order
dev/hook_error_correlation/analyze.py:19 L3-infra-content FunctionDef
dev/hook_error_correlation/analyze.py:84 L7-stepdown-order load_fires out of call order
dev/hook_smoke/probe_bg_task_live.py:20 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/hook_smoke/probe_bg_task_live.py:23 L5-orchestrator-logic BinOp
dev/hook_smoke/probe_bg_task_live.py:24 L5-orchestrator-logic BinOp
dev/hook_smoke/probe_bg_task_live.py:25 L5-orchestrator-logic IfExp
dev/hook_smoke/probe_bg_task_live.py:185 L6-guard-not-single-call guard body is not one statement
dev/hook_smoke/probe_replay_cli_chained.py:29 L5-orchestrator-logic DictComp
dev/hook_smoke/probe_replay_cli_chained.py:30 L5-orchestrator-logic For
dev/hook_smoke/probe_replay_cli_chained.py:35 L5-orchestrator-logic GeneratorExp
dev/hook_smoke/probe_replay_cli_chained.py:36 L5-orchestrator-logic GeneratorExp
dev/hook_smoke/probe_replay_cli_chained.py:38 L5-orchestrator-logic For
dev/hook_smoke/run_all.py:51 L7-stepdown-order _strand_names out of call order
dev/hook_smoke/test_bg_task_detection.py:96 L3-functions-content Assign
dev/hook_smoke/test_block_po_read.py:22 L3-infra-content FunctionDef
dev/hook_smoke/test_block_rag_cli_document_repeat.py:31 L7-stepdown-order _run_hook out of call order
dev/hook_smoke/test_block_rag_corpus_read.py:80 L7-stepdown-order _message_runners out of call order
dev/hook_smoke/test_block_worker_kill_while_working.py:100 L7-stepdown-order make_stub out of call order
dev/hook_smoke/test_block_worker_send_while_working.py:88 L7-stepdown-order make_stub out of call order
dev/hook_smoke/test_fire_log.py:32 L7-stepdown-order _last_record out of call order
dev/hook_smoke/test_header_capture.py:146 L6-guard-not-single-call guard body is not one statement
dev/hook_smoke/test_header_capture.py:146 L6-script-without-orchestrator 16 functions
dev/hook_smoke/test_hook_setup_main_branch_gate.py:78 L7-stepdown-order make_git_stub out of call order
dev/hook_smoke/test_hook_trace_lines.py:37 L7-stepdown-order _run_hook out of call order
dev/hook_smoke/test_log_janitor.py:14 L3-infra-content FunctionDef
dev/hook_smoke/test_rewrite_background_sleep.py:132 L7-stepdown-order _cwd_for_kind out of call order
dev/hook_smoke/verify_bg_task_detection_live.py:23 L5-orchestrator-logic BinOp
dev/hook_smoke/verify_bg_task_detection_live.py:24 L5-orchestrator-logic IfExp
dev/hook_smoke/verify_bg_task_detection_live.py:29 L7-stepdown-order _scratch_tasks_base out of call order
dev/hotkey_latency/analyze_latency.py:25 L5-orchestrator-logic IfExp
dev/hotkey_latency/analyze_latency.py:30 L5-orchestrator-logic BinOp
dev/hotkey_latency/analyze_latency.py:64 L7-stepdown-order _pct out of call order
dev/hotkey_latency/probe_get_event_time.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/hotkey_latency/probe_get_event_time.py:16 L3-infra-content ClassDef
dev/hotkey_latency/probe_get_event_time.py:19 L3-infra-content ClassDef
dev/hotkey_latency/probe_get_event_time.py:95 L4-orchestrator-not-one-function 2 nodes, 1 functions
dev/hotkey_latency/probe_get_event_time.py:16 L7-stepdown-order _EventHotKeyID out of call order
dev/jsonl/A_extract_cache_turns_proof.py:43 L7-stepdown-order _load_messages out of call order
dev/jsonl/test_jsonl_reader.py:19 L5-orchestrator-logic With
dev/jsonl/test_jsonl_reader.py:21 L5-orchestrator-logic For
dev/jsonl/test_jsonl_reader.py:23 L5-orchestrator-logic IfExp
dev/jsonl/test_jsonl_reader.py:27 L7-stepdown-order run_strand out of call order
dev/menubar/discover_byte_identity.py:93 L3-functions-content Assign
dev/menubar/discover_byte_identity.py:135 L3-functions-content Assign
dev/menubar/discover_byte_identity.py:18 L5-orchestrator-logic ListComp
dev/menubar/discover_byte_identity.py:100 L7-stepdown-order _install_fakes out of call order
dev/menubar/model_controller_byte_identity.py:30 L5-orchestrator-logic Try
dev/menubar/model_controller_byte_identity.py:89 L7-stepdown-order _safe_call out of call order
dev/menubar/p5_g1_log.py:19 L7-stepdown-order strip_ts out of call order
dev/menubar/p5_g3_app.py:20 L7-stepdown-order _Obj out of call order
dev/menubar/p5_g4_detection.py:23 L7-stepdown-order _FakeCG out of call order
dev/menubar/p5_g5_discover.py:26 L7-stepdown-order _Dir out of call order
dev/menubar/p5_g6_caches.py:29 L7-stepdown-order run_result out of call order
dev/menubar/p5_g7_model.py:27 L7-stepdown-order _Fake out of call order
dev/menubar/p5_run_all.py:14 L5-orchestrator-logic With
dev/menubar/panel_manager_byte_identity.py:23 L5-orchestrator-logic Try
dev/menubar/panel_manager_byte_identity.py:40 L7-stepdown-order _make_sessions out of call order
dev/menubar_nspanel/menubar_debug.py:22 L5-orchestrator-logic Try
dev/menubar_nspanel/menubar_debug.py:52 L6-guard-not-single-call guard body is not one statement
dev/menubar_nspanel/p1_nspanel_probe.py:53 L7-stepdown-order _PanelController out of call order
dev/message_strip_fp_nuke/audit_scan.py:42 L3-infra-content Delete
dev/model_selector/verify_four_tab_ring.py:31 L5-orchestrator-logic With
dev/model_selector/verify_four_tab_ring.py:40 L5-orchestrator-logic BinOp
dev/model_selector/verify_four_tab_ring.py:45 L7-stepdown-order _only_open out of call order
dev/model_selector/verify_hook17_removal.py:12 L4-orchestrator-not-one-function 5 nodes, 5 functions
dev/model_selector/verify_hook17_removal.py:29 L5-orchestrator-logic BinOp
dev/model_selector/verify_hook17_removal.py:33 L5-orchestrator-logic BinOp
dev/model_selector/verify_hook17_removal.py:34 L5-orchestrator-logic UnaryOp
dev/model_selector/verify_hook17_removal.py:39 L5-orchestrator-logic ListComp
dev/model_selector/verify_hook17_removal.py:40 L5-orchestrator-logic Compare
dev/model_selector/verify_hook17_removal.py:48 L5-orchestrator-logic With
dev/model_selector/verify_hook_writer_split.py:18 L5-orchestrator-logic With
dev/model_selector/verify_hook_writer_split.py:44 L5-orchestrator-logic BinOp
dev/model_selector/verify_hook_writer_split.py:49 L7-stepdown-order _without_clock out of call order
dev/monitor_lifecycle/probe_monitor_load.py:16 L5-orchestrator-logic Lambda
dev/monitor_root/test_monitor_root.py:26 L5-orchestrator-logic With
dev/monitor_root/test_monitor_root.py:34 L7-stepdown-order collect_cases out of call order
dev/native-model-start/model_override_injection_tests.py:46 L3-infra-content FunctionDef
dev/native-model-start/p2_model_params_probe.py:51 L5-orchestrator-logic BinOp
dev/native-model-start/p3_cache_breakpoints_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/native-model-start/p3_cache_breakpoints_probe.py:262 L5-orchestrator-logic Import
dev/native-model-start/p3_cache_breakpoints_probe.py:263 L5-orchestrator-logic For
dev/native-model-start/p3_cache_breakpoints_probe.py:26 L7-stepdown-order _FakeHeaders out of call order
dev/native-model-start/p4_dual_log_integrity_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/native-model-start/p4_dual_log_integrity_probe.py:214 L5-orchestrator-logic For
dev/native-model-start/p4_dual_log_integrity_probe.py:236 L5-orchestrator-logic BinOp
dev/native-model-start/p4_dual_log_integrity_probe.py:30 L7-stepdown-order _load_session_requests out of call order
dev/native-model-start/p5_strip_wordings_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/native-model-start/p5_strip_wordings_probe.py:30 L7-stepdown-order _load_session_requests out of call order
dev/nsgridview_migration/probe.py:2 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/nsgridview_migration/probe.py:160 L4-orchestrator-not-one-function 3 nodes, 1 functions
dev/nsgridview_migration/probe.py:170 L5-orchestrator-logic Lambda
dev/nsgridview_migration/probe.py:181 L5-orchestrator-logic BinOp
dev/nsgridview_migration/probe.py:182 L5-orchestrator-logic BinOp
dev/nsgridview_migration/probe.py:191 L6-module-level-call main()
dev/nsgridview_migration/probe.py:43 L7-stepdown-order _cell_btn out of call order
dev/pane_error_log/p1_shared.py:21 L3-infra-content ClassDef
dev/pane_error_log/p1_shared.py:25 L3-infra-content ClassDef
dev/pane_flicker/bench_hover_render.py:22 L5-orchestrator-logic Try
dev/pane_flicker/bench_hover_render.py:47 L7-stepdown-order _render_once out of call order
dev/pane_flicker/m1_frame_e2e_driver.py:135 L3-functions-content Assign
dev/pane_flicker/m1_frame_e2e_test.py:28 L5-orchestrator-logic With
dev/pane_flicker/m1_frame_e2e_test.py:34 L5-orchestrator-logic IfExp
dev/pane_flicker/m1_frame_e2e_test.py:38 L7-stepdown-order run_all_strands out of call order
dev/pane_flicker/m1_strand_abort_test.py:17 L5-orchestrator-logic With
dev/pane_flicker/m2_byte_identity_test.py:24 L5-orchestrator-logic With
dev/pane_flicker/m2_byte_identity_test.py:30 L5-orchestrator-logic IfExp
dev/pane_flicker/m2_hover_timing.py:40 L7-stepdown-order extract_old_tree out of call order
dev/pane_flicker/m2_state_sequence_driver.py:24 L5-orchestrator-logic Lambda
dev/pane_flicker/m2_state_sequence_driver.py:28 L5-orchestrator-logic With
dev/pane_flicker/m2_state_sequence_driver.py:96 L7-stepdown-order snapshot out of call order
dev/pane_flicker/observe_timestamp_order.py:19 L5-orchestrator-logic AugAssign
dev/pane_flicker/observe_timestamp_order.py:20 L5-orchestrator-logic AugAssign
dev/pane_flicker/observe_timestamp_order.py:27 L7-stepdown-order _note_skipped_line out of call order
dev/pane_flicker/run_scenarios.py:20 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:22 L5-orchestrator-logic With
dev/pane_flicker/run_scenarios.py:24 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:25 L5-orchestrator-logic ListComp
dev/pane_flicker/run_scenarios.py:27 L5-orchestrator-logic BoolOp
dev/pane_flicker/run_scenarios.py:28 L5-orchestrator-logic IfExp
dev/pane_flicker/run_scenarios.py:29 L5-orchestrator-logic IfExp
dev/pane_flicker/run_scenarios.py:44 L7-stepdown-order _load out of call order
dev/pane_flicker/scenario_lib.py:23 L3-infra-content FunctionDef
dev/pane_flicker/scenario_run.py:222 L3-functions-content Assign
dev/pane_flicker/scenario_run.py:19 L5-orchestrator-logic Try
dev/pane_search/p1_full_sweep_cost_probe.py:28 L5-orchestrator-logic Delete
dev/pane_search/p1_full_sweep_cost_probe.py:32 L5-orchestrator-logic Delete
dev/pane_search/p1_full_sweep_cost_probe.py:43 L5-orchestrator-logic BinOp
dev/pane_search/p1_full_sweep_cost_probe.py:49 L6-guard-not-single-call guard body is not one statement
dev/pane_search/p5_worker_proxy_pane_parity_fixtures.py:27 L3-infra-content ClassDef
dev/panes/render_byte_identity.py:16 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/panes/render_byte_identity.py:20 L5-orchestrator-logic ImportFrom
dev/panes/test_display_tripwires.py:19 L5-orchestrator-logic With
dev/panes/test_display_tripwires.py:21 L5-orchestrator-logic For
dev/panes/test_display_tripwires.py:23 L5-orchestrator-logic IfExp
dev/panes/test_display_tripwires.py:27 L7-stepdown-order run_strand out of call order
dev/pipeline/io_profile/01_poll_cycle_cost.py:23 L3-infra-content FunctionDef
dev/pipeline/io_profile/01_poll_cycle_cost.py:28 L3-infra-content FunctionDef
dev/pipeline/io_profile/01_poll_cycle_cost.py:33 L3-infra-content FunctionDef
dev/pipeline/io_profile/01_poll_cycle_cost.py:23 L7-stepdown-order _counting_stat out of call order
dev/proxy/addon_hook_byte_identity.py:28 L5-orchestrator-logic With
dev/proxy/addon_hook_byte_identity.py:46 L7-stepdown-order _note_skipped_line out of call order
dev/proxy/pipeline_byte_identity.py:24 L5-orchestrator-logic For
dev/proxy/pipeline_byte_identity.py:34 L7-stepdown-order _note_skipped_line out of call order
dev/proxy/replay_env_context_strip.py:19 L3-infra-content Delete
dev/proxy/replay_env_context_strip.py:67 L3-functions-content Assign
dev/proxy/replay_env_context_strip.py:68 L3-functions-content Assign
dev/proxy/replay_env_context_strip.py:44 L5-orchestrator-logic For
dev/proxy/replay_env_context_strip.py:200 L6-guard-not-single-call guard body is not one statement
dev/proxy/replay_env_context_strip.py:75 L7-stepdown-order _form_of out of call order
dev/proxy/replay_sn_notice_strip.py:17 L3-infra-content Delete
dev/proxy/replay_sn_notice_strip.py:37 L7-stepdown-order _reconstruct_matches out of call order
dev/proxy/replay_strip_v2.py:49 L7-stepdown-order _note_skipped_line out of call order
dev/proxy/scan_sr_catalog.py:50 L5-orchestrator-logic GeneratorExp
dev/proxy/scan_sr_catalog.py:51 L5-orchestrator-logic GeneratorExp
dev/proxy/scan_sr_catalog.py:62 L7-stepdown-order _note_skipped_line out of call order
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
dev/proxy/test_proxy_start_fallbacks.py:88 L3-functions-content Assign
dev/proxy/test_proxy_start_fallbacks.py:20 L5-orchestrator-logic BinOp
dev/proxy/test_proxy_start_fallbacks.py:22 L5-orchestrator-logic Try
dev/proxy/test_strip_fix_cases_badge.py:17 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_badge_nudge.py:10 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_badge_nudge.py:12 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_git_attribution.py:31 L3-infra-content FunctionDef
dev/proxy/test_strip_fix_cases_git_attribution.py:35 L3-infra-content FunctionDef
dev/proxy/test_strip_fix_cases_launch_ack_interrupt.py:168 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_launch_ack_interrupt.py:169 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_wrapped_tn.py:7 L3-functions-content Assign
dev/proxy/test_strip_fix_cases_wrapped_tn.py:9 L3-functions-content Assign
dev/proxy/verify_proxy_start_equivalence.py:63 L3-functions-content For
dev/proxy/verify_proxy_start_equivalence.py:32 L5-orchestrator-logic BinOp
dev/proxy/verify_proxy_start_equivalence.py:35 L5-orchestrator-logic Try
dev/proxy_analysis/01_session_summary.py:243 L6-guard-not-single-call guard body is not one statement
dev/proxy_analysis/01_session_summary.py:38 L7-stepdown-order _note_skipped_line out of call order
dev/proxy_display/test_forwarded_tripwires.py:18 L5-orchestrator-logic With
dev/proxy_display/test_forwarded_tripwires.py:20 L5-orchestrator-logic For
dev/proxy_display/test_forwarded_tripwires.py:22 L5-orchestrator-logic IfExp
dev/proxy_display/test_forwarded_tripwires.py:26 L7-stepdown-order run_strand out of call order
dev/proxy_display/test_pd10_lazy_messages.py:19 L5-orchestrator-logic With
dev/proxy_display/test_pd10_lazy_messages.py:21 L5-orchestrator-logic For
dev/proxy_display/test_pd10_lazy_messages.py:23 L5-orchestrator-logic IfExp
dev/proxy_display/test_pd10_lazy_messages.py:27 L7-stepdown-order run_strand out of call order
dev/proxy_display/test_session_marker_states.py:18 L5-orchestrator-logic With
dev/proxy_display/test_session_marker_states.py:20 L5-orchestrator-logic For
dev/proxy_display/test_session_marker_states.py:22 L5-orchestrator-logic IfExp
dev/proxy_display/test_session_marker_states.py:26 L7-stepdown-order run_strand out of call order
dev/proxy_display/verify_req_numbering.py:16 L4-orchestrator-not-one-function 3 nodes, 3 functions
dev/proxy_display/verify_req_numbering.py:19 L5-orchestrator-logic ImportFrom
dev/proxy_display/verify_req_numbering.py:23 L5-orchestrator-logic ImportFrom
dev/proxy_dual_log/A_render_refactor_proof/A_render_refactor_proof.py:9 L3-infra-content While
dev/proxy_dual_log/A_render_refactor_proof/A_render_refactor_proof.py:18 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/proxy_dual_log/A_render_refactor_proof/A_render_refactor_proof.py:21 L5-orchestrator-logic ImportFrom
dev/proxy_dual_log/attribution_coverage/attribution_coverage.py:10 L3-infra-content While
dev/proxy_dual_log/attribution_coverage/attribution_coverage.py:15 L3-infra-content FunctionDef
dev/proxy_dual_log/attribution_coverage/attribution_coverage.py:45 L5-orchestrator-logic BinOp
dev/proxy_dual_log/attribution_coverage/attribution_coverage_report.py:9 L3-infra-content While
dev/proxy_dual_log/diff_strip_inject.py:8 L3-infra-content While
dev/proxy_dual_log/diff_strip_inject.py:239 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/diff_strip_inject.py:63 L7-stepdown-order _infer_family out of call order
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:11 L3-infra-content While
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py:212 L4-orchestrator-not-one-function 0 nodes, 0 functions
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe_cases.py:9 L3-infra-content While
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe_cases.py:14 L3-infra-content FunctionDef
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:17 L3-infra-content While
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:68 L5-orchestrator-logic FunctionDef
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:73 L5-orchestrator-logic ListComp
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:76 L5-orchestrator-logic For
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:84 L5-orchestrator-logic BinOp
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:85 L5-orchestrator-logic With
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py:23 L7-stepdown-order _emit_intro out of call order
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_spans_cases.py:8 L3-infra-content While
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_spans_cases.py:13 L3-infra-content FunctionDef
dev/proxy_dual_log/main_log_elimination_probe/main_log_elimination_probe.py:43 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/main_log_elimination_probe/main_log_elimination_report.py:8 L3-infra-content While
dev/proxy_dual_log/proxy_176_bg_launch_ack_tests/proxy_176_bg_launch_ack_tests.py:6 L3-infra-content While
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:8 L3-infra-content While
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:13 L3-infra-content FunctionDef
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:40 L5-orchestrator-logic BinOp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:41 L5-orchestrator-logic BinOp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:51 L5-orchestrator-logic ListComp
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py:56 L5-orchestrator-logic BinOp
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:13 L3-infra-content While
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:189 L5-orchestrator-logic ImportFrom
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:195 L5-orchestrator-logic BinOp
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:198 L5-orchestrator-logic FunctionDef
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:207 L5-orchestrator-logic With
dev/proxy_dual_log/test_composition_invariant/composition_probe.py:19 L7-stepdown-order fmt_spans out of call order
dev/proxy_dual_log/test_composition_invariant/composition_probe_corpus.py:9 L3-infra-content While
dev/proxy_dual_log/test_composition_invariant/composition_probe_corpus.py:14 L3-infra-content FunctionDef
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:11 L3-infra-content While
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:100 L5-orchestrator-logic Compare
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:104 L5-orchestrator-logic BinOp
dev/proxy_dual_log/test_composition_invariant/test_composition_invariant.py:26 L7-stepdown-order load_fixture out of call order
dev/proxy_dual_log/tt_delta_skip_replay.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_dual_log/tt_delta_skip_replay.py:9 L3-infra-content While
dev/proxy_dual_log/tt_delta_skip_replay.py:48 L3-infra-content FunctionDef
dev/proxy_dual_log/tt_delta_skip_replay.py:189 L4-orchestrator-not-one-function 7 nodes, 7 functions
dev/proxy_dual_log/tt_delta_skip_replay.py:193 L5-orchestrator-logic For
dev/proxy_dual_log/tt_delta_skip_replay.py:202 L5-orchestrator-logic For
dev/proxy_dual_log/tt_delta_skip_replay.py:207 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:208 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:222 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:224 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:226 L5-orchestrator-logic BinOp
dev/proxy_dual_log/tt_delta_skip_replay.py:227 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:230 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:233 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:236 L5-orchestrator-logic BoolOp
dev/proxy_dual_log/tt_delta_skip_replay.py:254 L5-orchestrator-logic IfExp
dev/proxy_dual_log/tt_delta_skip_replay.py:255 L5-orchestrator-logic IfExp
dev/proxy_dual_log/tt_delta_skip_replay.py:259 L5-orchestrator-logic SetComp
dev/proxy_dual_log/tt_delta_skip_replay.py:264 L5-orchestrator-logic GeneratorExp
dev/proxy_dual_log/tt_delta_skip_replay.py:271 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/verify_delta.py:41 L5-orchestrator-logic ListComp
dev/proxy_dual_log/verify_delta.py:42 L5-orchestrator-logic IfExp
dev/proxy_dual_log/verify_delta.py:261 L6-guard-not-single-call guard body is not one statement
dev/proxy_dual_log/verify_delta.py:75 L7-stepdown-order _advance_chain out of call order
dev/proxy_forensics/strip_tracking_audit.py:49 L6-guard-not-single-call guard body is not one statement
dev/proxy_forensics/strip_tracking_audit.py:49 L6-script-without-orchestrator 2 functions
dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py:29 L5-orchestrator-logic For
dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py:35 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/p4_blocklist_223_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_instrumentation/p4_blocklist_223_probe.py:21 L7-stepdown-order _select_session_stem out of call order
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:98 L5-orchestrator-logic For
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:102 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:105 L5-orchestrator-logic For
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:107 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:108 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py:21 L7-stepdown-order _load_messages_for_flow out of call order
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:218 L5-orchestrator-logic BoolOp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:226 L5-orchestrator-logic For
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:241 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:242 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:244 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:245 L5-orchestrator-logic IfExp
dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py:29 L7-stepdown-order _load_session out of call order
dev/proxy_instrumentation/p7_blocklist_258_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_instrumentation/p7_blocklist_258_probe.py:202 L5-orchestrator-logic AugAssign
dev/proxy_instrumentation/p7_blocklist_258_probe.py:22 L7-stepdown-order _all_original_logs out of call order
dev/proxy_instrumentation/post_restart_verification.py:75 L7-stepdown-order _iter_jsonl out of call order
dev/proxy_instrumentation/render_recorded_request.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_instrumentation/render_recorded_request.py:60 L3-functions-content Assign
dev/proxy_instrumentation/render_recorded_request.py:61 L3-functions-content Assign
dev/proxy_instrumentation/render_recorded_request.py:82 L5-orchestrator-logic ImportFrom
dev/proxy_instrumentation/render_recorded_request.py:90 L5-orchestrator-logic Compare
dev/proxy_instrumentation/render_recorded_request.py:92 L5-orchestrator-logic For
dev/proxy_instrumentation/render_recorded_request.py:95 L5-orchestrator-logic For
dev/proxy_instrumentation/render_recorded_request.py:98 L5-orchestrator-logic BinOp
dev/proxy_instrumentation/render_recorded_request.py:103 L5-orchestrator-logic Compare
dev/proxy_instrumentation/render_recorded_request.py:105 L5-orchestrator-logic For
dev/proxy_instrumentation/render_recorded_request.py:19 L7-stepdown-order _verify_target_line_index out of call order
dev/proxy_instrumentation/response_model_corpus_report.py:40 L7-stepdown-order _init_stats_acc out of call order
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:54 L5-orchestrator-logic For
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:88 L5-orchestrator-logic For
dev/proxy_tool_stripping/probe_trailing_message_shapes.py:23 L7-stepdown-order _all_stripped_texts out of call order
dev/ram_audit/dump_byte_identity.py:32 L7-stepdown-order _fake_provider out of call order
dev/refactoring/layout_scan.py:88 L7-stepdown-order node_start out of call order
dev/refactoring/strand_runner.py:23 L5-orchestrator-logic IfExp
dev/refactoring/strand_runner_selftest.py:43 L5-orchestrator-logic With
dev/session_analysis/01_extract.py:12 L4-orchestrator-not-one-function 5 nodes, 5 functions
dev/session_analysis/01_extract.py:52 L5-orchestrator-logic ListComp
dev/session_analysis/01_extract.py:54 L5-orchestrator-logic For
dev/session_analysis/02_cache_timeline.py:11 L4-orchestrator-not-one-function 4 nodes, 4 functions
dev/session_analysis/03_cache_rebuild_context.py:15 L4-orchestrator-not-one-function 3 nodes, 3 functions
dev/session_analysis/03_cache_rebuild_context.py:36 L5-orchestrator-logic For
dev/session_analysis/03_cache_rebuild_context.py:48 L5-orchestrator-logic For
dev/session_analysis/04_cache_validation.py:39 L5-orchestrator-logic BinOp
dev/session_analysis/04_cache_validation.py:45 L5-orchestrator-logic IfExp
dev/session_analysis/04_cache_validation.py:62 L7-stepdown-order _find_cc_breakpoints out of call order
dev/session_analysis/05_req_breakdown.py:20 L5-orchestrator-logic IfExp
dev/session_analysis/05_req_breakdown.py:39 L5-orchestrator-logic BinOp
dev/session_analysis/07_quartet_prefix_diff.py:23 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:30 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:31 L5-orchestrator-logic IfExp
dev/session_analysis/07_quartet_prefix_diff.py:32 L5-orchestrator-logic BinOp
dev/session_analysis/07_quartet_prefix_diff.py:33 L5-orchestrator-logic ListComp
dev/session_analysis/07_quartet_prefix_diff.py:40 L5-orchestrator-logic ListComp
dev/session_analysis/07_quartet_prefix_diff.py:49 L5-orchestrator-logic BinOp
dev/session_launcher/p2_panel_snapshot.py:29 L5-orchestrator-logic BinOp
dev/session_launcher/p2_panel_snapshot.py:47 L7-stepdown-order _imp out of call order
dev/session_launcher/s0_preflight.py:43 L7-stepdown-order _run out of call order
dev/session_launcher/s1_switch_probe.py:29 L5-orchestrator-logic BinOp
dev/session_launcher/s1_switch_probe.py:34 L5-orchestrator-logic For
dev/session_launcher/s1_switch_probe.py:51 L7-stepdown-order _direction_right out of call order
dev/session_launcher/s2_ghostty_window_probe.py:32 L5-orchestrator-logic BinOp
dev/session_launcher/s2_ghostty_window_probe.py:36 L5-orchestrator-logic For
dev/session_launcher/s2_ghostty_window_probe.py:61 L7-stepdown-order _new_window_script out of call order
dev/session_launcher/space_lib.py:281 L3-functions-content Assign
dev/session_launcher/t1_autojump_removal.py:32 L5-orchestrator-logic ListComp
dev/session_launcher/t1_autojump_removal.py:36 L5-orchestrator-logic GeneratorExp
dev/session_launcher/t1_autojump_removal.py:41 L7-stepdown-order _run_check out of call order
dev/session_launcher/t2_launch_tab.py:44 L5-orchestrator-logic With
dev/session_launcher/t2_launch_tab.py:50 L5-orchestrator-logic GeneratorExp
dev/session_launcher/t2_launch_tab.py:60 L7-stepdown-order _spawn_case out of call order
dev/session_launcher/t3_tab_click.py:271 L3-functions-content Assign
dev/session_launcher/t3_tab_click.py:36 L5-orchestrator-logic With
dev/session_launcher/t3_tab_click.py:42 L5-orchestrator-logic GeneratorExp
dev/session_launcher/t3_tab_click.py:52 L7-stepdown-order _spawn_case out of call order
dev/setup_py2app/exit_on_failure_checks.py:19 L5-orchestrator-logic BinOp
dev/setup_py2app/exit_on_failure_checks.py:20 L5-orchestrator-logic For
dev/setup_py2app/exit_on_failure_checks.py:22 L5-orchestrator-logic ListComp
dev/setup_py2app/exit_on_failure_checks.py:23 L5-orchestrator-logic BinOp
dev/setup_py2app/exit_on_failure_checks.py:24 L5-orchestrator-logic IfExp
dev/setup_py2app/exit_on_failure_checks.py:30 L7-stepdown-order _load_functions out of call order
dev/skill_picker/p1_real_discovery.py:25 L5-orchestrator-logic ListComp
dev/skill_picker/p1_real_discovery.py:26 L5-orchestrator-logic IfExp
dev/skill_picker/t1_skill_picker.py:45 L5-orchestrator-logic With
dev/skill_picker/t1_skill_picker.py:49 L5-orchestrator-logic BinOp
dev/skill_picker/t1_skill_picker.py:53 L5-orchestrator-logic GeneratorExp
dev/skill_picker/t1_skill_picker.py:63 L7-stepdown-order _spawn_case out of call order
dev/sleep_pattern_analysis/analyze.py:19 L5-orchestrator-logic IfExp
dev/thinking/render_brain_badge.py:106 L6-guard-not-single-call guard body is not one statement
dev/thinking/render_thinking_expander.py:229 L6-guard-not-single-call guard body is not one statement
dev/thinking/render_thinking_expander.py:42 L7-stepdown-order _owning_entry_thinking_blocks out of call order
dev/timer-loop/p1_scan_bg_completion_wordings.py:20 L5-orchestrator-logic IfExp
dev/timer-loop/p1_scan_bg_completion_wordings.py:21 L5-orchestrator-logic GeneratorExp
dev/timer-loop/p1_scan_bg_completion_wordings.py:32 L5-orchestrator-logic For
dev/timer-loop/p1_scan_bg_completion_wordings.py:41 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:1 L2-marker-order INFRASTRUCTURE -> FUNCTIONS -> ORCHESTRATOR
dev/timer-loop/p3_project_scope_incident_probe.py:24 L3-infra-content FunctionDef
dev/timer-loop/p3_project_scope_incident_probe.py:30 L3-infra-content FunctionDef
dev/timer-loop/p3_project_scope_incident_probe.py:171 L4-orchestrator-not-one-function 2 nodes, 2 functions
dev/timer-loop/p3_project_scope_incident_probe.py:173 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:175 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:183 L5-orchestrator-logic GeneratorExp
dev/timer-loop/p3_project_scope_incident_probe.py:184 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:186 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:188 L5-orchestrator-logic Compare
dev/timer-loop/p3_project_scope_incident_probe.py:206 L5-orchestrator-logic For
dev/timer-loop/p3_project_scope_incident_probe.py:208 L5-orchestrator-logic BinOp
dev/timer-loop/p3_project_scope_incident_probe.py:212 L6-guard-not-single-call guard body is not one statement
dev/tmux_launcher/fallback_tripwire_checks.py:30 L5-orchestrator-logic Try
dev/tmux_launcher/fallback_tripwire_checks.py:38 L5-orchestrator-logic ListComp
dev/tmux_launcher/fallback_tripwire_checks.py:39 L5-orchestrator-logic For
dev/tmux_launcher/fallback_tripwire_checks.py:41 L5-orchestrator-logic BinOp
dev/tmux_launcher/fallback_tripwire_checks.py:42 L5-orchestrator-logic IfExp
dev/tmux_launcher/fallback_tripwire_checks.py:59 L7-stepdown-order _new_session out of call order
dev/tool_injection/01_extract_schemas.py:61 L5-orchestrator-logic For
dev/tool_injection/01_extract_schemas.py:72 L5-orchestrator-logic For
dev/tool_injection/01_extract_schemas.py:76 L5-orchestrator-logic For
dev/tool_use_analysis/cc_injection_audit.py:14 L3-infra-content FunctionDef
dev/tool_use_analysis/cc_injection_audit.py:45 L5-orchestrator-logic For
dev/tool_use_analysis/cc_injection_audit.py:291 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/cc_injection_audit.py:109 L7-stepdown-order _normalize_msg_content out of call order
dev/tool_use_analysis/extract_long_calls.py:26 L5-orchestrator-logic Lambda
dev/tool_use_analysis/extract_long_calls.py:33 L5-orchestrator-logic ListComp
dev/tool_use_analysis/extract_long_calls.py:36 L5-orchestrator-logic ListComp
dev/tool_use_analysis/extract_long_calls.py:37 L5-orchestrator-logic Lambda
dev/tool_use_analysis/extract_long_calls.py:73 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_long_calls_lib.py:20 L3-infra-content ClassDef
dev/tool_use_analysis/extract_long_calls_lib.py:37 L3-infra-content ClassDef
dev/tool_use_analysis/extract_long_calls_lib.py:48 L3-infra-content ClassDef
dev/tool_use_analysis/extract_long_calls_lib.py:58 L3-infra-content ClassDef
dev/tool_use_analysis/extract_long_calls_lib.py:69 L3-infra-content ClassDef
dev/tool_use_analysis/extract_patterns.py:20 L5-orchestrator-logic For
dev/tool_use_analysis/extract_patterns.py:66 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_transcript.py:20 L5-orchestrator-logic For
dev/tool_use_analysis/extract_transcript.py:34 L5-orchestrator-logic BinOp
dev/tool_use_analysis/extract_transcript.py:36 L5-orchestrator-logic With
dev/tool_use_analysis/extract_transcript.py:158 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_transcript.py:74 L7-stepdown-order _result_to_text out of call order
dev/tool_use_analysis/extract_zeros.py:25 L5-orchestrator-logic For
dev/tool_use_analysis/extract_zeros.py:341 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/extract_zeros.py:117 L7-stepdown-order is_zero_result out of call order
dev/tool_use_analysis/rag_query_audit.py:28 L3-infra-content ClassDef
dev/tool_use_analysis/rag_query_audit.py:38 L3-infra-content ClassDef
dev/tool_use_analysis/rag_query_audit.py:44 L3-infra-content ClassDef
dev/tool_use_analysis/rag_query_audit.py:56 L5-orchestrator-logic For
dev/tool_use_analysis/rag_query_audit.py:312 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/rag_query_audit.py:28 L7-stepdown-order RagCall out of call order
dev/tool_use_analysis/rag_truncation_audit.py:19 L5-orchestrator-logic For
dev/tool_use_analysis/rag_truncation_audit.py:46 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/rs_truncation_preserve_replay.py:90 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/sr_bypass_audit.py:30 L3-infra-content If
dev/tool_use_analysis/sr_bypass_audit.py:41 L5-orchestrator-logic For
dev/tool_use_analysis/sr_bypass_audit.py:222 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/sr_session_audit.py:39 L5-orchestrator-logic BoolOp
dev/tool_use_analysis/sr_session_audit.py:41 L5-orchestrator-logic DictComp
dev/tool_use_analysis/sr_session_audit.py:45 L5-orchestrator-logic For
dev/tool_use_analysis/sr_session_audit.py:70 L5-orchestrator-logic BinOp
dev/tool_use_analysis/sr_session_audit.py:80 L7-stepdown-order _iter_sessions out of call order
dev/tool_use_analysis/strip_audit.py:26 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:28 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:29 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:30 L5-orchestrator-logic AugAssign
dev/tool_use_analysis/strip_audit.py:68 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/tag_presence_audit.py:15 L3-infra-content If
dev/tool_use_analysis/tag_presence_audit.py:76 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/waste_repetition.py:285 L6-guard-not-single-call guard body is not one statement
dev/tool_use_analysis/waste_repetition.py:99 L7-stepdown-order _sig out of call order
dev/tool_use_errors/A_error_cluster_audit.py:14 L3-infra-content FunctionDef
dev/verbosity/extract_turns.py:1 L1-no-marker module has code but no section marker
dev/worker_pane_split/attach_worker_stats_cost_probe.py:118 L7-stepdown-order _fake_workers_for_paths out of call order
dev/worker_status_probes/probe_a.py:16 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_a.py:17 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_a.py:33 L7-stepdown-order _get_window_activity out of call order
dev/worker_status_probes/probe_b.py:24 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_b.py:25 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_b.py:42 L7-stepdown-order _safe_name out of call order
dev/worker_status_probes/probe_c.py:21 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_c.py:22 L5-orchestrator-logic Lambda
dev/worker_status_probes/probe_c.py:38 L7-stepdown-order _get_window0_pane_ids out of call order
dev/worker_status_probes/run_all.py:32 L5-orchestrator-logic BinOp
dev/worker_status_probes/run_all.py:38 L5-orchestrator-logic Lambda
dev/worker_status_probes/run_all.py:39 L5-orchestrator-logic Lambda
dev/worker_status_probes/run_all.py:43 L5-orchestrator-logic For
dev/worker_status_probes/run_all.py:81 L7-stepdown-order _launch_probes out of call order
dev/workers/test_worker_probes.py:21 L5-orchestrator-logic With
dev/workers/test_worker_probes.py:23 L5-orchestrator-logic For
dev/workers/test_worker_probes.py:25 L5-orchestrator-logic IfExp
dev/workers/test_worker_probes.py:29 L7-stepdown-order run_strand out of call order
