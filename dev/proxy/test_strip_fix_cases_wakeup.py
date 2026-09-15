# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    check, tool_result_str, tool_result_list, text_block,
    _apply_first_pass, _apply_bg_exit_strip, _apply_sn_notice_strip, _apply_role_system_strip,
    _WAKEUP_TEXT, _SN_NOTICE_PARAGRAPH,
)

# FUNCTIONS

def _has_wakeup(content) -> bool:
    """Return True if _WAKEUP_TEXT (stripped of trailing newline) appears in content."""
    core = _WAKEUP_TEXT.rstrip('\n')
    if isinstance(content, str):
        return core in content
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get('type') == 'text' and core in b.get('text', '')
            for b in content
        )
    return False


# ── WAKEUP FALSE-POSITIVE TESTS ───────────────────────────────────────────────

# W01 — <task-notification> in tool_result str → TN branch must NOT fire
def w01_tn_in_tool_result_str():
    tn_data = 'RAG result: <task-notification><status>completed</status><summary>done</summary></task-notification>'
    msgs = [{'role': 'user', 'content': tool_result_str(tn_data)}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    content = new_msgs[0]['content']
    check('W01_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W01_tn_mod_not_fired', not any('task_notification' in m for m in mods), f'mods: {mods}')
    check('W01_tool_result_intact', new_msgs[0]['content'][0]['content'] == tn_data)


# W02 — <task-notification> in tool_result list-of-text → TN branch must NOT fire
def w02_tn_in_tool_result_list():
    tn_data = 'source: <task-notification><status>failed</status><summary></summary></task-notification>'
    msgs = [{'role': 'user', 'content': tool_result_list(tn_data)}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    content = new_msgs[0]['content']
    check('W02_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W02_tn_mod_not_fired', not any('task_notification' in m for m in mods), f'mods: {mods}')
    check('W02_tool_result_intact', new_msgs[0]['content'][0]['content'][0]['text'] == tn_data)


# W03 — complete BGK pattern in tool_result str → BGK branch must NOT fire, data intact
def w03_bgk_in_tool_result_str():
    bgk_data = 'log: Background command "sleep 600" completed (exit code 143)\n'
    msgs = [{'role': 'user', 'content': tool_result_str(bgk_data)}]
    new_msgs, mods, _, _c, _, _ops = _apply_bg_exit_strip(msgs)
    content = new_msgs[0]['content']
    check('W03_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W03_bgk_mod_not_fired', 'replaced_bg_completed_text' not in mods, f'mods: {mods}')
    check('W03_tool_result_intact', new_msgs[0]['content'][0]['content'] == bgk_data)


# W04 — genuine plain-string completed TN → wakeup injected, mod=trimmed_task_notification
# fixture has no <task-id> and no <output-file> — doubles as the "both missing" case: neither
# 'Output:' nor 'ID:' line, content reduces to exactly _WAKEUP_TEXT.
def w04_genuine_tn_completed_plain_string():
    tn = '<task-notification>\n<status>completed</status>\n<summary>Background command "sleep 10" completed (exit code 0)</summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    check('W04_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W04_mod_trimmed', 'trimmed_task_notification' in mods, f'mods: {mods}')
    check('W04_no_output_line', 'Output:' not in new_msgs[0]['content'], repr(new_msgs[0]['content']))
    check('W04_no_id_line', 'ID:' not in new_msgs[0]['content'], repr(new_msgs[0]['content']))
    check('W04_reduces_to_bare_wakeup', new_msgs[0]['content'] == _WAKEUP_TEXT, repr(new_msgs[0]['content']))


# W05 — genuine plain-string failed TN → wakeup injected, mod=replaced_task_notification
def w05_genuine_tn_failed_plain_string():
    tn = '<task-notification>\n<status>failed</status>\n<summary></summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    check('W05_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W05_mod_replaced', 'replaced_task_notification' in mods, f'mods: {mods}')
    check('W05_no_output_line', 'Output:' not in new_msgs[0]['content'], repr(new_msgs[0]['content']))
    check('W05_no_id_line', 'ID:' not in new_msgs[0]['content'], repr(new_msgs[0]['content']))


# W06 — genuine plain-string BGK kill notification → wakeup injected, mod=replaced_bg_completed_text
def w06_genuine_bgk_plain_string():
    bgk = 'Background command "sleep 600" completed (exit code 143)\n'
    msgs = [{'role': 'user', 'content': bgk}]
    new_msgs, mods, _, _c, _, _ops = _apply_bg_exit_strip(msgs)
    check('W06_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W06_mod_replaced', 'replaced_bg_completed_text' in mods, f'mods: {mods}')


# ── SN-NOTICE-PARAGRAPH TESTS ─────────────────────────────────────────────────
# strip_sn_notice.py — bare 4-line paragraph ahead of <task-notification>, anchored startswith
# decision (not substring-anywhere) — same FP-nuke class as bg_launch_ack / plan_mode, see
# process-docs/message_strip_fp_nuke/.

# W07 — genuine plain-string paragraph + <task-notification> tag → stripped, mod fired
def w07_sn_notice_genuine_plain_string():
    tn = '<task-notification>\n<status>completed</status>\n<summary>done</summary>\n</task-notification>\n'
    content = _SN_NOTICE_PARAGRAPH + '\n\n' + tn
    msgs = [{'role': 'user', 'content': content}]
    new_msgs, mods, _, _c, _, _ops = _apply_sn_notice_strip(msgs)
    result = new_msgs[0]['content']
    check('W07_sn_notice_stripped', _SN_NOTICE_PARAGRAPH not in result, repr(result)[:80])
    check('W07_tn_tag_preserved', result == tn, repr(result))
    check('W07_mod_fired', 'stripped_sn_notice_paragraph' in mods, f'mods: {mods}')


# W08 — genuine text-block at non-zero block index → stripped (do NOT hardcode index 0)
def w08_sn_notice_text_block_index_one():
    tn = '<task-notification>\n<status>failed</status>\n<summary></summary>\n</task-notification>\n'
    content = [
        {'type': 'text', 'text': 'preceding unrelated block'},
        {'type': 'text', 'text': _SN_NOTICE_PARAGRAPH + '\n\n' + tn},
    ]
    msgs = [{'role': 'user', 'content': content}]
    new_msgs, mods, _, _c, _, _ops = _apply_sn_notice_strip(msgs)
    result = new_msgs[0]['content']
    check('W08_block0_untouched', result[0]['text'] == 'preceding unrelated block')
    check('W08_block1_stripped', result[1]['text'] == tn, repr(result[1]['text']))
    check('W08_mod_fired', 'stripped_sn_notice_paragraph' in mods, f'mods: {mods}')


# W09 — paragraph quoted as tool_result data → must NOT fire, byte-exact untouched
def w09_sn_notice_tool_result_untouched():
    data = 'log excerpt:\n' + _SN_NOTICE_PARAGRAPH + '\nend of excerpt'
    msgs = [{'role': 'user', 'content': tool_result_str(data)}]
    new_msgs, mods, _, _c, _, _ops = _apply_sn_notice_strip(msgs)
    check('W09_tool_result_intact', new_msgs[0]['content'][0]['content'] == data)
    check('W09_mod_not_fired', 'stripped_sn_notice_paragraph' not in mods, f'mods: {mods}')


# W10 — paragraph mid-content in a text block (not at start) → must NOT fire, untouched
def w10_sn_notice_mid_content_untouched():
    text = 'user note before it:\n' + _SN_NOTICE_PARAGRAPH + '\n\nmore text after'
    msgs = [{'role': 'user', 'content': text_block(text)}]
    new_msgs, mods, _, _c, _, _ops = _apply_sn_notice_strip(msgs)
    check('W10_mid_content_intact', new_msgs[0]['content'][0]['text'] == text)
    check('W10_mod_not_fired', 'stripped_sn_notice_paragraph' not in mods, f'mods: {mods}')


# W11 — role="system" with paragraph at start → NOT touched by the SN-notice pass (out of scope)
def w11_sn_notice_role_system_untouched():
    content = _SN_NOTICE_PARAGRAPH + '\n\nsome trailing detail'
    msgs = [{'role': 'system', 'content': content}]
    new_msgs, mods, _, _c, _, _ops = _apply_sn_notice_strip(msgs)
    check('W11_role_system_intact', new_msgs[0]['content'] == content)
    check('W11_mod_not_fired', 'stripped_sn_notice_paragraph' not in mods, f'mods: {mods}')


# ── ROLE=SYSTEM TASK-NOTIFICATION TESTS (2026-07-29 fix) ─────────────────────
# _apply_role_system_strip previously nuked EVERY role='system' message to '.' before any TN
# handling could see it — CC delivers bg-task wake-ups as a plain-str role='system' message
# (measured: 173/280 real TN occurrences in one session log, role='system'/str; the other 107
# were role='user'/list-text, already handled). Fix: _apply_role_system_strip leaves TN-carrying
# role='system' messages untouched; _apply_sn_notice_strip + _apply_first_pass's TN branch (both
# widened to accept role='system', narrowly gated on the TN tag itself) do the actual wake-up
# construction — single source of truth, no duplicated TN-building logic. These tests run the
# real 3-pass sequence (role_system_strip -> sn_notice_strip -> first_pass) matching rules.py's
# `_passes` order.

def w12_role_system_tn_completed_full_pipeline():
    tn = ('<task-notification>\n<task-id>abc123</task-id>\n<status>completed</status>\n'
          '<summary>Background command "sleep 10" completed (exit code 0)</summary>\n'
          '</task-notification>')
    content = _SN_NOTICE_PARAGRAPH + '\n\n' + tn
    messages = [{'role': 'system', 'content': content}]
    messages, _m1, _, _, _, _ = _apply_role_system_strip(messages)
    messages, _m2, _, _, _, _ = _apply_sn_notice_strip(messages)
    messages, mods3, _, _, _, _ = _apply_first_pass(messages)
    result = messages[0]['content']
    check('W12_not_nuked_to_dot', result != '.', repr(result))
    check('W12_wakeup_present', _has_wakeup(result), repr(result))
    check('W12_sn_notice_gone', _SN_NOTICE_PARAGRAPH not in result, repr(result))
    check('W12_role_preserved', messages[0]['role'] == 'system')
    check('W12_mod_trimmed', 'trimmed_task_notification' in mods3, f'mods3: {mods3}')
    check('W12_id_line_present', 'ID: abc123' in result, repr(result))
    check('W12_no_output_line', 'Output:' not in result, repr(result))


def w13_role_system_tn_failed_with_output_file():
    tn = ('<task-notification>\n<task-id>xyz789</task-id>\n'
          '<output-file>/tmp/foo/task.output</output-file>\n<status>failed</status>\n'
          '<summary>Background command "x" failed with exit code 42</summary>\n'
          '</task-notification>')
    content = _SN_NOTICE_PARAGRAPH + '\n\n' + tn
    messages = [{'role': 'system', 'content': content}]
    messages, _m1, _, _, _, _ = _apply_role_system_strip(messages)
    messages, _m2, _, _, _, _ = _apply_sn_notice_strip(messages)
    messages, mods3, _, _, _, _ = _apply_first_pass(messages)
    result = messages[0]['content']
    check('W13_wakeup_present', _has_wakeup(result), repr(result))
    check('W13_output_line_present', 'Output: /tmp/foo/task.output' in result, repr(result))
    check('W13_mod_replaced', 'replaced_task_notification' in mods3, f'mods3: {mods3}')
    check('W13_id_line_present', 'ID: xyz789' in result, repr(result))
    check('W13_line_order', result.index('Output:') < result.index('ID:'), repr(result))


def w14_role_system_noise_still_nuked_through_full_chain():
    messages = [{'role': 'system', 'content': "The date has changed. Today's date is now 2026-04-22."}]
    messages, mods1, _, _, _, _ = _apply_role_system_strip(messages)
    messages, _m2, _, _, _, _ = _apply_sn_notice_strip(messages)
    messages, _m3, _, _, _, _ = _apply_first_pass(messages)
    check('W14_noise_nuked', messages[0]['content'] == '.', repr(messages[0]['content']))
    check('W14_mod_recorded', 'stripped_role_system_msg' in mods1, f'mods1: {mods1}')


# W30 — CC 2.1.223 mid-turn user message (role='system') preserved whole (issue #61). Pre-223 this
# arrived as a role='user' <system-reminder> ('user-interrupt' template, PARTIAL mode in
# strip_sr.py — IMPORTANT line stripped, user body kept). The 223 role=system form bypasses that
# SR-based guard entirely and was falling through to _apply_role_system_strip's unconditional '.'
# replacement, silently dropping the user's text before it reached the model. Real body (recorded
# session api_requests_opus_posts_1786051932, msg 274): 'jetzt' + CC's own boilerplate explainer.
def w30_role_system_mid_turn_user_msg_preserved_whole():
    real_body = (
        'The user sent a new message while you were working:\njetzt\n\n'
        'This is how Claude Code surfaces messages the user sends mid-turn — within the running '
        'turn, often alongside the next tool result, rather than as a separate conversation turn. '
        'Address the message above as you continue this turn.'
    )
    messages = [{'role': 'system', 'content': real_body}]
    new_messages, mods, removed, changed_idxs, injected, ops = _apply_role_system_strip(messages)
    check('W30_content_untouched', new_messages[0]['content'] == real_body, repr(new_messages[0]['content']))
    check('W30_user_text_present', 'jetzt' in new_messages[0]['content'])
    check('W30_role_preserved', new_messages[0]['role'] == 'system')
    check('W30_mod_not_fired', 'stripped_role_system_msg' not in mods, f'mods: {mods}')
    check('W30_no_changed_index', changed_idxs == [], f'changed_idxs: {changed_idxs}')
    check('W30_no_removed_recorded', removed == {}, f'removed: {removed}')
    check('W30_no_ops_recorded', ops == {}, f'ops: {ops}')

    # Leading whitespace before the marker — guard checks lstrip()'d text, not exact prefix.
    padded = '  \n' + real_body
    messages2 = [{'role': 'system', 'content': padded}]
    new_messages2, mods2, _, _, _, _ = _apply_role_system_strip(messages2)
    check('W30_leading_whitespace_still_preserved', new_messages2[0]['content'] == padded, repr(new_messages2[0]['content']))
    check('W30_leading_whitespace_mod_not_fired', 'stripped_role_system_msg' not in mods2)
