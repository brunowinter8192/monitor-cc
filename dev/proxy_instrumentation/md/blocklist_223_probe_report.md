# CC 2.1.223 TOOL_BLOCKLIST extension probe

Session (newest main-session log in live corpus): `api_requests_opus_monitor_cc_1789408648`

| case | pass | detail |
|---|---|---|
| post_strip_set_is_exact | PASS | orig=['Agent', 'Artifact', 'AskUserQuestion', 'Bash', 'DeferredToolPlaceholder', 'Edit', 'ListAgents', 'Read', 'ReportFindings', 'ScheduleWakeup', 'SendFeedback', 'Skill', 'ToolSearch', 'Workflow', 'Write'] kept=['Bash', 'Read', 'Skill'] (non-MCP kept: ['Bash', 'Read', 'Skill'], want ['Bash', 'Read', 'Skill'], mcp_extra=[]) |
| newly_blocked_actually_removed | PASS | removed_names contains all of ['Artifact', 'DeferredToolPlaceholder', 'ReportFindings']: True (removed=['Agent', 'Artifact', 'AskUserQuestion', 'DeferredToolPlaceholder', 'Edit', 'ListAgents', 'ReportFindings', 'ScheduleWakeup', 'SendFeedback', 'ToolSearch', 'Workflow', 'Write']) |
| no_live_tool_use_for_newly_blocked | PASS | tool_use invocations of newly-blocked names in session messages: (none) |
| agent_absent_from_forwarded | PASS | 'Agent' in forwarded tools_names (real pipeline, pre-existing blocklist entry): False (forwarded union=['Bash', 'Read', 'Skill']) — confirms strip fires; drill-down sighting was the intentional whole-stripped display row, not a strip-path bug |
| blocklist_contains_new_entries | PASS | ['Artifact', 'DeferredToolPlaceholder', 'ReportFindings'] subset of TOOL_BLOCKLIST: True |

## Overall: ALL PASS