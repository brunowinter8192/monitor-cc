#!/usr/bin/env python3
"""Unit tests for tool_result strip-isolation fix (T1-T8).
Run: python3 dev/proxy/test_strip_fix.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

from src.proxy.strip_sr import (
    _strip_system_reminder, _strip_all_system_reminders,
    _strip_plan_mode_blocks, _strip_user_interrupt_sr,
)
from src.proxy.payload_helpers import (
    _content_contains, _find_system_reminder_blocks, _strip_task_notification_tags,
)
from src.proxy.content_strip import _message_has_rejection, _strip_rejection_message

_SR_OPEN = '<system-reminder>'
_SR_CLOSE = '</system-reminder>'
_MARKER = 'task tools haven'

PASS = []
FAIL = []

def check(name, condition, msg=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {msg}' if msg else ''))


# T1: echter SR in text-block → wird korrekt gestripped
def t1_real_sr_in_text_block():
    content = [
        {'type': 'text', 'text': f'{_SR_OPEN}task tools haven\'t been used{_SR_CLOSE} hello'}
    ]
    result = _strip_system_reminder(content, _MARKER)
    text = result[0]['text']
    check('T1_sr_removed_from_text', _SR_OPEN not in text)
    check('T1_rest_preserved', 'hello' in text)


# T2: SR-Literal als String in tool_result.content → bleibt unverändert
def t2_sr_literal_in_tool_result_string():
    literal = f'if {_SR_OPEN} in text: return "system-reminder"'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal}
    ]
    result = _strip_system_reminder(content, _MARKER)
    check('T2_tool_result_string_intact', result[0]['content'] == literal, repr(result[0]['content'][:60]))


# T3: SR-Literal in {type: text} sub-block in tool_result list → bleibt unverändert
def t3_sr_literal_in_tool_result_subblock():
    literal = f'Code: {_SR_OPEN}task tools haven\'t{_SR_CLOSE}'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': [
            {'type': 'text', 'text': literal}
        ]}
    ]
    result = _strip_system_reminder(content, _MARKER)
    inner = result[0]['content'][0]['text']
    check('T3_tool_result_subblock_intact', inner == literal, repr(inner[:60]))


# T4: echter SR in text-block + SR-Literal in tool_result im selben Message → nur text-block-SR entfernt
def t4_mixed_message():
    literal = f'if {_SR_OPEN} in x: pass'
    real_sr = f'{_SR_OPEN}task tools haven\'t been used recently.{_SR_CLOSE}'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal},
        {'type': 'text', 'text': f'{real_sr} user message here'},
    ]
    result = _strip_system_reminder(content, _MARKER)
    tool_inner = result[0]['content']
    text_after = result[1]['text']
    check('T4_tool_result_intact', tool_inner == literal, repr(tool_inner[:60]))
    check('T4_real_sr_removed', _SR_OPEN not in text_after, repr(text_after[:60]))
    check('T4_user_text_preserved', 'user message here' in text_after)


# T5: _content_contains mit SR-Literal in tool_result → returns False
def t5_content_contains_tool_result_false():
    literal = f'if {_SR_OPEN} in x: pass'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal}
    ]
    result = _content_contains(content, _SR_OPEN)
    check('T5_no_trigger_from_tool_result_literal', result is False, f'got {result}')


# T6: _content_contains mit echtem SR in text-block → returns True
def t6_content_contains_text_block_true():
    content = [
        {'type': 'text', 'text': f'{_SR_OPEN}task tools haven{_SR_CLOSE}'}
    ]
    result = _content_contains(content, _MARKER)
    check('T6_trigger_from_text_block', result is True, f'got {result}')


# T7: Rejection-Marker in tool_result → _message_has_rejection findet es (Non-regression)
def t7_rejection_nonregression():
    REJECTION = "The user doesn't want to proceed with this tool use"
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': REJECTION}
    ]
    found = _message_has_rejection(content)
    stripped = _strip_rejection_message(content)
    check('T7_rejection_detected', found is True, f'got {found}')
    check('T7_rejection_stripped', stripped[0]['content'] == '.', repr(stripped[0]['content']))


# T8: <task-notification> in tool_result → _strip_task_notification_tags lässt es unverändert
def t8_task_notification_in_tool_result():
    literal = '<task-notification><summary>some task</summary></task-notification>'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal}
    ]
    result = _strip_task_notification_tags(content)
    check('T8_task_notif_in_tool_result_intact', result[0]['content'] == literal, repr(result[0]['content'][:60]))


# Cross-check: _strip_all_system_reminders also skips tool_result
def t9_strip_all_skips_tool_result():
    literal = f'code: {_SR_OPEN}anything{_SR_CLOSE}'
    real_sr = f'{_SR_OPEN}real reminder{_SR_CLOSE}'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal},
        {'type': 'text', 'text': real_sr},
    ]
    result = _strip_all_system_reminders(content)
    check('T9_all_strip_tool_result_intact', result[0]['content'] == literal)
    check('T9_all_strip_real_sr_removed', _SR_OPEN not in result[1]['text'])


# Cross-check: _find_system_reminder_blocks skips tool_result
def t10_find_sr_blocks_skips_tool_result():
    literal_in_tool_result = f'{_SR_OPEN}task tools haven{_SR_CLOSE}'
    real_sr = f'{_SR_OPEN}task tools haven{_SR_CLOSE}'
    content = [
        {'type': 'tool_result', 'tool_use_id': 'x', 'content': literal_in_tool_result},
        {'type': 'text', 'text': real_sr},
    ]
    found = _find_system_reminder_blocks(content, _MARKER)
    check('T10_find_sr_returns_only_text_block', len(found) == 1, f'found {len(found)}: {found}')


if __name__ == '__main__':
    print('Running T1-T10...\n')
    for fn in [t1_real_sr_in_text_block, t2_sr_literal_in_tool_result_string,
               t3_sr_literal_in_tool_result_subblock, t4_mixed_message,
               t5_content_contains_tool_result_false, t6_content_contains_text_block_true,
               t7_rejection_nonregression, t8_task_notification_in_tool_result,
               t9_strip_all_skips_tool_result, t10_find_sr_blocks_skips_tool_result]:
        fn()

    print(f'\n{len(PASS)}/{len(PASS)+len(FAIL)} passed')
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)
    print('ALL PASS')
