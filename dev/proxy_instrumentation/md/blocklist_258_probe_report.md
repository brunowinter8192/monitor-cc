# CC 2.1.258 + Edit/Write TOOL_BLOCKLIST extension probe

Newest main-session log: `api_requests_opus_monitor_cc_1789401523_original.jsonl`
Corpus files scanned for live tool_use: 12

| case | pass | detail |
|---|---|---|
| post_strip_set_is_exact | PASS | log=api_requests_opus_monitor_cc_1789401523_original.jsonl orig=['Agent', 'Artifact', 'AskUserQuestion', 'Bash', 'DeferredToolPlaceholder', 'Edit', 'ListAgents', 'Read', 'ReportFindings', 'ScheduleWakeup', 'SendFeedback', 'Skill', 'ToolSearch', 'Workflow', 'Write'] kept=['Bash', 'Read', 'Skill'] (non-MCP kept: ['Bash', 'Read', 'Skill'], want ['Bash', 'Read', 'Skill'], mcp_extra=[]) |
| newly_blocked_actually_removed | PASS | removed_names contains all of ['ListAgents', 'SendFeedback']: True (removed=['Agent', 'Artifact', 'AskUserQuestion', 'DeferredToolPlaceholder', 'Edit', 'ListAgents', 'ReportFindings', 'ScheduleWakeup', 'SendFeedback', 'ToolSearch', 'Workflow', 'Write']) |
| no_live_tool_use_for_newly_blocked_corpus_wide | PASS | files scanned: 12, tool_use hits for ['ListAgents', 'SendFeedback']: 0  |
| blocklist_contains_new_entries | PASS | ['ListAgents', 'SendFeedback'] subset of TOOL_BLOCKLIST: True |
| rw_blocklist_contains_new_entries | PASS | ['Edit', 'Write'] subset of TOOL_BLOCKLIST: True |
| rw_actually_removed_from_representative_payload | PASS | removed_names contains all of ['Edit', 'Write']: True (removed=['Agent', 'Artifact', 'AskUserQuestion', 'DeferredToolPlaceholder', 'Edit', 'ListAgents', 'ReportFindings', 'ScheduleWakeup', 'SendFeedback', 'ToolSearch', 'Workflow', 'Write']) |
| rw_live_tool_use_present_corpus_wide_by_design | FAIL | files scanned: 12, tool_use hits for ['Edit', 'Write']: 0 across 0 file(s) — UNLIKE checks 2/3 above, hits are EXPECTED here (Edit/Write are among the dominant tools of every running session; this is the residual risk documented for this milestone, not a bug) |
| rw_historic_tool_use_result_left_untouched_documented_gap | PASS | for each of ['Edit', 'Write'], a synthetic historic tool_use/tool_result pair survives _strip_unused_tools + _strip_blocked_tool_references byte-for-byte: [('Edit', True, True), ('Write', True, True)] (both functions only ever touch the tools schema array and tool_reference content blocks — this pins the documented gap, it does not close it) |

## Overall: FAILURES PRESENT