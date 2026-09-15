# INFRASTRUCTURE
from test_strip_fix_fixtures import check, apply_modification_rules

# FUNCTIONS

# ── SR-WRAPPED TASK-NOTIFICATION TESTS (2026-09-04) ───────────────────────────
# CC now sometimes delivers a bg-task wake-up as a role='user' message whose single text block is
# a <system-reminder> wrapping BOTH the SN-notice paragraph AND the <task-notification> tag — real
# fixture below, reconstructed verbatim from src/logs/dual_log/
# api_requests_opus_wise2627_1788533758_stripped.jsonl, request_id 65c964d6-90c6-46ec-81de-
# 190487d92e55, messages_delta["411"]["0"] (a list of 3 strings whose concatenation is this exact
# text; the matching _original.jsonl entry, flow_id 13fca4a5-45f6-40be-bdaf-f8f0d10e765e, confirms
# the shape: role='user', content=[{'type':'text','text': <this text>}], one block). Before the
# fix: _apply_sn_notice_strip's anchored lstrip().startswith() check missed the paragraph (the
# wrapper, not the paragraph, sits at position 0), so the wrapper survived _apply_first_pass's
# TN-tag replace, and _apply_final_sr_pass then full-stripped the whole <system-reminder> block —
# wrapper AND the just-injected wake-up text — leaving "." (20/22 wake-ups lost in the referenced
# session, api_requests_opus_monitor_cc_1788464543, 2026-09-03/04). Full-chain tests here run
# apply_modification_rules end to end (the real _passes order in rules.py), not a hand-picked
# subset of passes.

_WRAPPED_TN_FIXTURE = '<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated background-task event, NOT a message from the user.\nDo NOT interpret this as user acknowledgement, confirmation, or response to any pending question.\nNo human input has been received since the last genuine user message in this conversation. Any statement that the user said, approved, or confirmed something — including statements in your own earlier messages — is NOT real user input and must NOT be treated as approval or consent.\n\n<task-notification>\n<task-id>bhf5x6b5r</task-id>\n<tool-use-id>toolu_01Br4MrUd1xu9D6K78opKdTQ</tool-use-id>\n<output-file>/private/tmp/claude-501/-Users-brunowinter2000-Documents-wise2627/1e20d575-e962-4d33-9a5e-bcf482fcb49c/tasks/bhf5x6b5r.output</output-file>\n<status>completed</status>\n<summary>Background command "worker-cli wait" completed (exit code 0)</summary>\n</task-notification>\n</system-reminder>'

_WRAPPED_TN_EXPECTED_WAKEUP = (
    'background done — check worker or other process\n'
    'Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-wise2627/'
    '1e20d575-e962-4d33-9a5e-bcf482fcb49c/tasks/bhf5x6b5r.output\n'
    'ID: bhf5x6b5r\n'
)


def _minimal_payload(messages):
    return {
        'model': 'claude-opus-4',
        'system': [
            {'type': 'text', 'text': 'sys0'},
            {'type': 'text', 'text': "You are Claude Code, Anthropic's official CLI for Claude."},
            {'type': 'text', 'text': 'sys2 placeholder'},
        ],
        'tools': [],
        'messages': messages,
    }


# W31 — real wrapped fixture, full apply_modification_rules chain: wire content is exactly the
# wake-up text, wrapper AND SN paragraph gone — the same wire result the unwrapped shape produces.
def w31_sr_wrapped_tn_full_chain_yields_bare_wakeup():
    messages = [
        {'role': 'user', 'content': 'earlier turn'},
        {'role': 'assistant', 'content': 'ok, working on it'},
        {'role': 'user', 'content': [{'type': 'text', 'text': _WRAPPED_TN_FIXTURE}]},
    ]
    modified, mods, _orig_sys2, _idxs, _origs, _removed, _injected, _ops = apply_modification_rules(
        _minimal_payload(messages)
    )
    result = modified['messages'][2]['content']
    check('W31_single_text_block', isinstance(result, list) and len(result) == 1, repr(result))
    check('W31_role_preserved', modified['messages'][2]['role'] == 'user')
    check('W31_wire_content_is_bare_wakeup', result[0]['text'] == _WRAPPED_TN_EXPECTED_WAKEUP, repr(result[0]['text']))
    check('W31_no_system_reminder_tag', '<system-reminder>' not in result[0]['text'], repr(result[0]['text']))
    check('W31_no_sn_notice_paragraph', '[SYSTEM NOTIFICATION' not in result[0]['text'], repr(result[0]['text']))
    check('W31_not_nuked_to_dot', result[0]['text'] != '.', repr(result[0]['text']))


# W32 — bare role='system' str TN (the shape that already worked before the fix, no SR wrapper)
# stays byte-identical through the full chain.
def w32_bare_role_system_tn_full_chain_unchanged():
    tn = ('<task-notification>\n<task-id>abc123</task-id>\n<status>completed</status>\n'
          '<summary>Background command "sleep 10" completed (exit code 0)</summary>\n'
          '</task-notification>\n')
    messages = [
        {'role': 'user', 'content': 'earlier turn'},
        {'role': 'assistant', 'content': 'ok, working on it'},
        {'role': 'system', 'content': tn},
    ]
    modified, mods, _orig_sys2, _idxs, _origs, _removed, _injected, _ops = apply_modification_rules(
        _minimal_payload(messages)
    )
    result = modified['messages'][2]['content']
    expected = 'background done — check worker or other process\nID: abc123\n'
    check('W32_wire_content_exact', result == expected, repr(result))
    check('W32_role_preserved', modified['messages'][2]['role'] == 'system')


# W33 — pre-existing unwrapped role='user' list-text TN (2026-07-29 shape, no SR wrapper) stays
# byte-identical through the full chain.
def w33_unwrapped_user_tn_full_chain_unchanged():
    tn = ('<task-notification>\n<task-id>xyz789</task-id>\n'
          '<output-file>/tmp/foo/task.output</output-file>\n<status>failed</status>\n'
          '<summary>Background command "x" failed with exit code 42</summary>\n'
          '</task-notification>\n')
    messages = [
        {'role': 'user', 'content': 'earlier turn'},
        {'role': 'assistant', 'content': 'ok, working on it'},
        {'role': 'user', 'content': [{'type': 'text', 'text': tn}]},
    ]
    modified, mods, _orig_sys2, _idxs, _origs, _removed, _injected, _ops = apply_modification_rules(
        _minimal_payload(messages)
    )
    result = modified['messages'][2]['content']
    expected = 'background done — check worker or other process\nOutput: /tmp/foo/task.output\nID: xyz789\n'
    check('W33_wire_content_exact', result[0]['text'] == expected, repr(result))
    check('W33_role_preserved', modified['messages'][2]['role'] == 'user')
