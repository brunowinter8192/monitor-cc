# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    check, tool_result_str, text_block,
    _strip_total_tokens_tail, _apply_total_tokens_tail_strip, apply_modification_rules,
    compose_block, _SN_NOTICE_PARAGRAPH,
)

_TASKS_DIR = '/private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/bb5299a5-a871-4c2e-9786-3cc7692e1f38/tasks'

_CACHE_CONTROL = {'type': 'ephemeral', 'ttl': '1h'}

_TAIL_111 = '<total_tokens>14985715 tokens left</total_tokens>'
_TAIL_68 = '<total_tokens>14997807 tokens left</total_tokens>'

_TN_111 = (
    '<task-notification>\n<task-id>bt3i3mnoz</task-id>\n'
    '<tool-use-id>toolu_01ANQMvhBfLLZicSxyocLSUf</tool-use-id>\n'
    f'<output-file>{_TASKS_DIR}/bt3i3mnoz.output</output-file>\n'
    '<status>completed</status>\n'
    '<summary>Background command "Auf Worker warten" completed (exit code 0)</summary>\n'
    '</task-notification>'
)

_ORIGINAL_111 = f'{_SN_NOTICE_PARAGRAPH}\n\n{_TN_111}\n\n{_TAIL_111}'

_FORWARDED_111_WITHOUT_TAIL = (
    'background done — check worker or other process\n'
    f'Output: {_TASKS_DIR}/bt3i3mnoz.output\n'
    'ID: bt3i3mnoz'
)


def _tn_68(task_id, tool_use_id, name):
    return (
        f'<task-notification>\n<task-id>{task_id}</task-id>\n<tool-use-id>{tool_use_id}</tool-use-id>\n'
        f'<output-file>{_TASKS_DIR}/{task_id}.output</output-file>\n<status>completed</status>\n'
        f'<summary>Background command "{name}" completed (exit code 0)</summary>\n</task-notification>'
    )


_ORIGINAL_68 = (
    f'{_SN_NOTICE_PARAGRAPH}\n\n{_tn_68("bsybgkxu3", "toolu_012625Uk4XoYzzNiT4oDypPT", "Auf die Haiku-Worker warten")}\n\n'
    f'{_SN_NOTICE_PARAGRAPH}\n\n{_tn_68("bsnr30gxg", "toolu_01AWD266dDHFDia2RJTTKmts", "Auf Worker warten")}\n\n'
    f'{_SN_NOTICE_PARAGRAPH}\n\n{_tn_68("bwpvupm90", "toolu_01XoPPqNi6SKor7cfedq3yAq", "Auf Küpper-Worker und viewerbg2 warten")}\n\n'
    f'{_TAIL_68}'
)

_WAKE_68 = (
    'background done — check worker or other process\n'
    f'Output: {_TASKS_DIR}/bsybgkxu3.output\n'
    'ID: bsybgkxu3'
)

_FORWARDED_68_WITHOUT_TAIL = (
    f'{_WAKE_68}\n\n{_SN_NOTICE_PARAGRAPH}\n\n{_WAKE_68}\n\n{_SN_NOTICE_PARAGRAPH}\n\n{_WAKE_68}'
)

_TRUNCATED_BODY = (
    "[Truncated: PARTIAL view — /tmp/pdf_KuepperControlling_2024/anchor_101-150.md: showing lines 1-327 of 1068 "
    "total (69236 tokens, cap 25000). Call Read with offset=328 limit=327 for the next page, or Grep to find a "
    "specific section.\n\n"
    "answer ONLY with a doc comment under that root (`create` an utterance, parent `<root id>`) — no "
    "artifact/platform comment tool: that relay thread is resolved and never reaches the doc; an edit asked "
    "there → `update` with `answering: \"<root id>\"`."
)
_TRUNCATED_TAIL = '<total_tokens>14997493 tokens left</total_tokens>'

_NUDGE_THEN_TAG = (
    "First privately list what you need next; then request every item that doesn't depend on another's result "
    "in this one response.\n\n<total_tokens>14986220 tokens left</total_tokens>"
)

_BARE_TAG = '<total_tokens>14979724 tokens left</total_tokens>'


def _run_pipeline(role: str, content):
    payload = {'system': [], 'messages': [{'role': role, 'content': content}]}
    modified, modifications, _sys2, _smi, _smo, removed_by_idx, _inj, _ops = apply_modification_rules(payload)
    return modified['messages'][0]['content'], modifications, removed_by_idx

# FUNCTIONS

def tl01_observed_111_list_block_with_cache_control():
    content = [{'type': 'text', 'text': _ORIGINAL_111, 'cache_control': _CACHE_CONTROL}]
    result, mods, _removed = _run_pipeline('system', content)
    check('TL01_exact_block', result == [{'type': 'text', 'text': _FORWARDED_111_WITHOUT_TAIL, 'cache_control': _CACHE_CONTROL}], result)
    check('TL01_mod_recorded', 'stripped_total_tokens_tail' in mods, mods)


def tl02_observed_113_plain_string():
    result, mods, _removed = _run_pipeline('system', _ORIGINAL_111)
    check('TL02_exact_string', result == _FORWARDED_111_WITHOUT_TAIL, repr(result))
    check('TL02_mod_recorded', 'stripped_total_tokens_tail' in mods, mods)


def tl03_observed_68_three_notifications_only_tail_removed():
    content = [{'type': 'text', 'text': _ORIGINAL_68, 'cache_control': _CACHE_CONTROL}]
    result, _mods, _removed = _run_pipeline('system', content)
    check('TL03_exact_block', result == [{'type': 'text', 'text': _FORWARDED_68_WITHOUT_TAIL, 'cache_control': _CACHE_CONTROL}], repr(result)[:600])
    check('TL03_no_tag_left', '<total_tokens>' not in result[0]['text'])


def tl04_observed_truncated_notice_list_shape_still_nuked_whole():
    original = f'{_TRUNCATED_BODY}\n\n{_TRUNCATED_TAIL}'
    result, mods, _removed = _run_pipeline('system', [{'type': 'text', 'text': original}])
    check('TL04_nuked_to_dot', result == '.' or result == [{'type': 'text', 'text': '.'}], result)
    check('TL04_tail_pass_not_involved', 'stripped_total_tokens_tail' not in mods, mods)


def tl05_observed_bare_marker_still_nuked_whole():
    result, mods, _removed = _run_pipeline('system', [{'type': 'text', 'text': _BARE_TAG}])
    check('TL05_nuked_to_dot', result == '.' or result == [{'type': 'text', 'text': '.'}], result)
    check('TL05_tail_pass_not_involved', 'stripped_total_tokens_tail' not in mods, mods)
    check('TL05_function_leaves_bare_marker', _strip_total_tokens_tail(_BARE_TAG) == (_BARE_TAG, []))


def tl06_observed_nudge_plus_tag_still_nuked_whole():
    result, mods, _removed = _run_pipeline('system', [{'type': 'text', 'text': _NUDGE_THEN_TAG}])
    check('TL06_nuked_to_dot', result == '.' or result == [{'type': 'text', 'text': '.'}], result)
    check('TL06_tail_pass_not_involved', 'stripped_total_tokens_tail' not in mods, mods)


def tl07_non_system_roles_untouched():
    quoted = f'the CC marker looks like this\n\n{_TAIL_111}'
    msgs = [
        {'role': 'user', 'content': quoted},
        {'role': 'assistant', 'content': text_block(quoted)},
        {'role': 'user', 'content': tool_result_str(quoted)},
    ]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_total_tokens_tail_strip(msgs)
    check('TL07_all_untouched', new_msgs == msgs)
    check('TL07_nothing_recorded', (mods, removed_by_idx, changed) == ([], {}, []))


def tl08_pass_records_mod_removed_and_second_run_is_noop():
    msgs = [{'role': 'system', 'content': f'{_FORWARDED_111_WITHOUT_TAIL}\n\n{_TAIL_111}'}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_total_tokens_tail_strip(msgs)
    check('TL08_content', new_msgs[0]['content'] == _FORWARDED_111_WITHOUT_TAIL, repr(new_msgs[0]['content']))
    check('TL08_mod_name', mods == ['stripped_total_tokens_tail'], mods)
    check('TL08_removed_is_tail_with_separator', removed_by_idx[0] == [f'\n\n{_TAIL_111}'], removed_by_idx)
    check('TL08_changed_index', changed == [0], changed)
    again, mods2, _r2, changed2, _i2, _o2 = _apply_total_tokens_tail_strip(new_msgs)
    check('TL08_second_run_noop', again == new_msgs and mods2 == [] and changed2 == [])


def tl09_ops_compose_to_stripped_tail_span():
    original = f'{_FORWARDED_111_WITHOUT_TAIL}\n\n{_TAIL_111}'
    _msgs, _mods, _removed, _changed, _inj, ops = _apply_total_tokens_tail_strip([{'role': 'system', 'content': original}])
    spans = compose_block(original, ops[0][0])
    stripped = ''.join(t for tag, t in spans if tag == 'stripped')
    equal = ''.join(t for tag, t in spans if tag == 'equal')
    check('TL09_stripped_span_is_tail', stripped == f'\n\n{_TAIL_111}', spans)
    check('TL09_equal_span_is_kept_text', equal == _FORWARDED_111_WITHOUT_TAIL, spans)
    check('TL09_no_injection', not any(tag == 'injected' for tag, _ in spans), spans)
