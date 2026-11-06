# INFRASTRUCTURE
from test_strip_fix_fixtures import check, _strip_unused_tools, _ph_mod

_OBSERVED_TOOL_NAMES = [
    'Agent', 'Artifact', 'AskUserQuestion', 'Bash', 'Edit', 'ListAgents', 'Read', 'ReportFindings',
    'ScheduleWakeup', 'SendFeedback', 'Skill', 'ToolSearch', 'Workflow', 'Write',
    'mcp__claude_ai_Claude_Docs__batch', 'mcp__claude_ai_Claude_Docs__guide',
    'DeferredToolPlaceholder', 'mcp__claude_ai_Claude_Docs__update', 'advisor',
]

_CLAUDE_AI_NAMES = [
    'mcp__claude_ai_Claude_Docs__batch', 'mcp__claude_ai_Claude_Docs__guide', 'mcp__claude_ai_Claude_Docs__update',
]

_ADVISOR_TOOL = {'type': 'advisor_20260301', 'name': 'advisor', 'model': 'claude-opus-5-5', 'defer_loading': True}

_SYNTHETIC_OTHER_MCP_NAME = 'mcp__plugin_iterative-dev_rag__search'

# FUNCTIONS

def _observed_tools() -> list:
    return [_ADVISOR_TOOL if n == 'advisor' else {'name': n, 'description': ''} for n in _OBSERVED_TOOL_NAMES]


def ca01_observed_opus_tool_list_loses_claude_ai_tools():
    payload = {'tools': _observed_tools()}
    modified, removed_count, removed_names = _strip_unused_tools(payload)
    kept = [t['name'] for t in modified['tools']]
    check('CA01_kept_exact', kept == ['Bash', 'Edit', 'Read', 'Skill', 'Write'], kept)
    check('CA01_removed_count', removed_count == 14, removed_count)
    check('CA01_advisor_reported', 'advisor' in removed_names, removed_names)
    check('CA01_claude_ai_names_reported', set(_CLAUDE_AI_NAMES) <= set(removed_names), removed_names)
    check('CA01_no_claude_ai_left', not any(n.startswith('mcp__claude_ai_') for n in kept), kept)


def ca02_advisor_entry_removed():
    payload = {'tools': _observed_tools()}
    modified, _count, removed_names = _strip_unused_tools(payload)
    check('CA02_advisor_gone', not any(t['name'] == 'advisor' for t in modified['tools']), modified['tools'])
    check('CA02_advisor_in_removed_names', removed_names.count('advisor') == 1, removed_names)
    check('CA02_input_payload_untouched', payload['tools'][-1] == _ADVISOR_TOOL, payload['tools'][-1])


def ca03_other_mcp_tools_untouched():
    other = {'name': _SYNTHETIC_OTHER_MCP_NAME, 'description': 'x'}
    payload = {'tools': [{'name': 'Bash'}, other, {'name': 'mcp__claude_ai_Claude_Docs__update'}]}
    modified, removed_count, removed_names = _strip_unused_tools(payload)
    check('CA03_other_mcp_kept', modified['tools'] == [{'name': 'Bash'}, other], modified['tools'])
    check('CA03_only_claude_ai_removed', (removed_count, removed_names) == (1, ['mcp__claude_ai_Claude_Docs__update']), removed_names)


def ca04_prefix_covers_unlisted_connector():
    payload = {'tools': [{'name': 'Read'}, {'name': 'mcp__claude_ai_Gmail__search_threads'}]}
    modified, removed_count, removed_names = _strip_unused_tools(payload)
    check('CA04_future_connector_removed', modified['tools'] == [{'name': 'Read'}], modified['tools'])
    check('CA04_reported', removed_names == ['mcp__claude_ai_Gmail__search_threads'], removed_names)


def ca05_clean_list_returns_same_payload_object():
    payload = {'tools': [{'name': 'Bash'}, {'name': 'Read'}]}
    modified, removed_count, removed_names = _strip_unused_tools(payload)
    check('CA05_same_object', modified is payload)
    check('CA05_nothing_removed', (removed_count, removed_names) == (0, []))


def ca06_advisor_tool_reference_removed_others_kept():
    ref = lambda n: {'type': 'tool_reference', 'tool_name': n}
    result = {'type': 'tool_result', 'tool_use_id': 't1', 'content': [ref('advisor'), ref('Bash'), {'type': 'text', 'text': 'x'}]}
    payload = {'messages': [{'role': 'user', 'content': [result]}]}
    modified = _ph_mod._strip_blocked_tool_references(payload)
    inner = modified['messages'][0]['content'][0]['content']
    check('CA06_advisor_reference_removed', inner == [ref('Bash'), {'type': 'text', 'text': 'x'}], inner)
    check('CA06_input_payload_untouched', len(result['content']) == 3, result['content'])
