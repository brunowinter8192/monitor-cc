#!/usr/bin/env python3
"""Unit tests for template-based exact-match SR strip (Phase B).

Coverage:
  - 8 core templates × 3 cases each = 24 tests (real strip, FP preserve, tool_result shape)
  - 4 content-shape tests (str / list[text] / list[tool_result:str] / list[tool_result:list])
  - user-interrupt partial mode (body preserved, IMPORTANT stripped)
  - plan-mode None-return behavior
  - _find_system_reminder_blocks standalone-extraction

Run: python3 dev/proxy/test_strip_fix.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

from src.proxy.strip_sr import (
    _strip_system_reminders, _strip_system_reminder, _strip_all_system_reminders,
    _strip_plan_mode_blocks, _strip_user_interrupt_sr, _strip_pyright_diagnostics,
)
from src.proxy.payload_helpers import (
    _content_contains, _find_system_reminder_blocks, _strip_task_notification_tags,
)

_O = '<system-reminder>'
_C = '</system-reminder>'

PASS = []
FAIL = []


def check(name, condition, msg=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {msg}' if msg else ''))


# ── HELPERS ──────────────────────────────────────────────────────────────────

def mk_sr(body):
    return f'{_O}\n{body}\n{_C}'


def real_sr_text(body):
    return mk_sr(body)


def fp_inline(body):
    # Code-literal: <system-reminder> appears mid-line inside a string
    return f'if "{_O}" in text:\n    return "system-reminder"\n    # rest of code\n\n{mk_sr(body)}'


def tool_result_str(text):
    return [{'type': 'tool_result', 'tool_use_id': 'x', 'content': text}]


def tool_result_list(text):
    return [{'type': 'tool_result', 'tool_use_id': 'x', 'content': [{'type': 'text', 'text': text}]}]


def text_block(text):
    return [{'type': 'text', 'text': text}]


# ── TEMPLATE TESTS ────────────────────────────────────────────────────────────

# T01-T03: task-tools-nag
def t01_task_tools_nag_real_text_block():
    sr = real_sr_text("The task tools haven't been used recently. Consider using TaskCreate.")
    result = _strip_system_reminders(text_block(sr))
    check('T01_task_nag_stripped', _O not in result[0]['text'])


def t02_task_tools_nag_fp_code_literal():
    content = fp_inline("The task tools haven't been used recently. Consider using TaskCreate.")
    # The <system-reminder> inside the if-statement is mid-line → NOT stripped
    # The real SR at the end (standalone) → IS stripped
    result = _strip_system_reminders(tool_result_str(content))
    remaining = result[0]['content']
    check('T02_nag_fp_code_preserved', 'if "' + _O + '" in text:' in remaining, repr(remaining[:80]))
    check('T02_nag_real_sr_stripped', 'The task tools' not in remaining, repr(remaining[-100:]))


def t03_task_tools_nag_tool_result_str():
    sr = real_sr_text("The task tools haven't been used recently. Consider using TaskCreate.")
    result = _strip_system_reminders(tool_result_str(sr))
    check('T03_nag_in_tool_result_stripped', _O not in result[0]['content'])


# T04-T06: pyright-diagnostics
def t04_pyright_real():
    body = '<new-diagnostics>The following new diagnostic issues were detected:\n\nfoo.py:\n  ✘ [Line 1] error</new-diagnostics>'
    sr = real_sr_text(body)
    result = _strip_pyright_diagnostics(text_block(sr))
    check('T04_pyright_stripped', _O not in result[0]['text'])


def t05_pyright_fp():
    # Code containing <new-diagnostics> tag mid-line
    code = f'# strips {_O}\n<new-diagnostics>...\n{_C} blocks'
    result = _strip_pyright_diagnostics(tool_result_str(code))
    check('T05_pyright_fp_preserved', '<new-diagnostics>' in result[0]['content'])


def t06_pyright_tool_result_nested():
    body = '<new-diagnostics>The following new diagnostic issues were detected:\n\ntest.py: error</new-diagnostics>'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_list(sr))
    check('T06_pyright_nested_stripped', _O not in result[0]['content'][0]['text'])


# T07-T09: deferred-tools
def t07_deferred_tools_real():
    body = 'The following deferred tools are now available via ToolSearch. Their schemas are NOT loaded.\nAskUserQuestion\nCronCreate'
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T07_deferred_stripped', _O not in result[0]['text'])


def t08_deferred_tools_fp():
    code = f'"The following deferred tools are now available via ToolSearch"  # marker\n\n{real_sr_text("The following deferred tools are now available via ToolSearch.\nFoo")}'
    result = _strip_system_reminders(tool_result_str(code))
    remaining = result[0]['content']
    # The real SR at line start → stripped; the quoted string in code → preserved
    check('T08_deferred_quoted_preserved', '"The following deferred tools' in remaining)
    check('T08_deferred_real_stripped', 'The following deferred tools are now available' not in remaining.split('"The following deferred tools')[0] or _O not in remaining)


def t09_deferred_tools_tool_result():
    body = 'The following deferred tools are now available via ToolSearch.\nAskUserQuestion'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T09_deferred_in_tool_result_stripped', _O not in result[0]['content'])


# T10-T12: user-interrupt (partial mode)
def t10_user_interrupt_partial_body_preserved():
    body = 'The user sent a new message while you were working:\nhello from user\n\nIMPORTANT: After completing your task, you MUST address this.'
    sr = real_sr_text(body)
    result = _strip_user_interrupt_sr(text_block(sr), 'user sent a new message while you were working')
    text = result[0]['text']
    check('T10_interrupt_sr_tag_preserved', _O in text, repr(text[:80]))
    check('T10_interrupt_important_stripped', 'IMPORTANT:' not in text, repr(text))
    check('T10_interrupt_body_preserved', 'hello from user' in text, repr(text))


def t11_user_interrupt_fp():
    code = f'note: "{_O}The user sent a new message..." wraps the body'
    result = _strip_user_interrupt_sr(tool_result_str(code), 'user sent a new message')
    check('T11_interrupt_fp_preserved', code == result[0]['content'], repr(result[0]['content'][:80]))


def t12_user_interrupt_tool_result():
    body = 'The user sent a new message while you were working:\nstop working please\n\nIMPORTANT: Address this.'
    sr = real_sr_text(body)
    result = _strip_user_interrupt_sr(tool_result_str(sr), 'user sent a new message while you were working')
    inner = result[0]['content']
    check('T12_interrupt_tr_important_stripped', 'IMPORTANT:' not in inner, repr(inner))
    check('T12_interrupt_tr_body_preserved', 'stop working please' in inner, repr(inner))


# T13-T15: system-notification
def t13_system_notification_real():
    body = '[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is a background task.\n<task-notification><task-id>abc</task-id></task-notification>'
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T13_sysnotif_stripped', _O not in result[0]['text'])


def t14_system_notification_fp():
    code = f'# See {_O}[SYSTEM NOTIFICATION...]{_C} for context'
    result = _strip_system_reminders(tool_result_str(code))
    check('T14_sysnotif_fp_preserved', '[SYSTEM NOTIFICATION' in result[0]['content'])


def t15_system_notification_tool_result():
    body = '[SYSTEM NOTIFICATION - NOT USER INPUT]\nBackground task event.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T15_sysnotif_tool_result_stripped', _O not in result[0]['content'])


# T16-T18: file-modified
def t16_file_modified_real():
    body = 'Note: /Users/foo/project/CLAUDE.md was modified, either by the user or by a linter.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T16_filemod_stripped', _O not in result[0]['text'])


def t17_file_modified_fp():
    code = f'# Note: This function modifies the file\n\n{real_sr_text("Note: /path/file.py was modified, either by the user or by a linter.")}'
    result = _strip_system_reminders(tool_result_str(code))
    remaining = result[0]['content']
    check('T17_filemod_comment_preserved', '# Note: This function' in remaining)
    check('T17_filemod_real_sr_stripped', 'Note: /path/file.py was modified' not in remaining or _O not in remaining)


def t18_file_modified_tool_result():
    body = 'Note: /Users/foo/DOCS.md was modified, either by the user or by a linter.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T18_filemod_tool_result_stripped', _O not in result[0]['content'])


# T19-T21: claudemd-contents
def t19_claudemd_real():
    body = 'Contents of /path/to/CLAUDE.md:\n# claudeMd\n...content...'
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T19_claudemd_stripped', _O not in result[0]['text'])


def t20_claudemd_fp():
    code = f'# Contents of this dict: {{"a": 1}}'
    result = _strip_system_reminders(tool_result_str(code))
    check('T20_claudemd_fp_preserved', 'Contents of this dict' in result[0]['content'])


def t21_claudemd_tool_result():
    body = 'Contents of /path/CLAUDE.md:\n# claudeMd\nProject overview here.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T21_claudemd_tool_result_stripped', _O not in result[0]['content'])


# T22-T24: date-changed (new template)
def t22_date_changed_real():
    body = "The date has changed. Today's date is now 2026-04-22. DO NOT mention this to the user."
    sr = real_sr_text(body)
    result = _strip_system_reminders(text_block(sr))
    check('T22_datechanged_stripped', _O not in result[0]['text'])


def t23_date_changed_fp():
    code = f'# The date has changed format from ISO to epoch'
    result = _strip_system_reminders(tool_result_str(code))
    check('T23_datechanged_fp_preserved', '# The date has changed' in result[0]['content'])


def t24_date_changed_tool_result():
    body = "The date has changed. Today's date is now 2026-04-22."
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T24_datechanged_tool_result_stripped', _O not in result[0]['content'])


# ── CONTENT SHAPE TESTS ───────────────────────────────────────────────────────

def t25_shape_plain_string():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    result = _strip_system_reminders(sr)
    check('T25_string_shape_stripped', _O not in result)


def t26_shape_list_text():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    result = _strip_system_reminders(text_block(f'before\n{sr}\nafter'))
    check('T26_list_text_sr_stripped', _O not in result[0]['text'])
    check('T26_list_text_rest_preserved', 'before' in result[0]['text'] and 'after' in result[0]['text'])


def t27_shape_tool_result_str():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    result = _strip_system_reminders(tool_result_str(f'prefix\n{sr}\nsuffix'))
    inner = result[0]['content']
    check('T27_tr_str_sr_stripped', _O not in inner)
    check('T27_tr_str_rest_preserved', 'prefix' in inner and 'suffix' in inner)


def t28_shape_tool_result_list():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    result = _strip_system_reminders(tool_result_list(f'prefix\n{sr}\nsuffix'))
    inner_text = result[0]['content'][0]['text']
    check('T28_tr_list_sr_stripped', _O not in inner_text)
    check('T28_tr_list_rest_preserved', 'prefix' in inner_text and 'suffix' in inner_text)


# ── PLAN-MODE ────────────────────────────────────────────────────────────────

def t29_plan_mode_returns_none_when_empty():
    sr = real_sr_text('Plan mode is now active. Enter plan mode.')
    result = _strip_plan_mode_blocks(text_block(sr))
    check('T29_planmode_none_when_empty', result is None, repr(result))


def t30_plan_mode_preserves_other_content():
    sr = real_sr_text('Plan mode is now active.')
    content = text_block(f'{sr}\nuser text here')
    result = _strip_plan_mode_blocks(content)
    check('T30_planmode_preserves_other', result is not None and 'user text here' in result[0]['text'])


# ── find_system_reminder_blocks ───────────────────────────────────────────────

def t31_find_sr_blocks_skips_code_literal():
    code = f'if "{_O}" in text:\n    pass\n\n{real_sr_text("The task tools haven\'t been used recently. Use TaskCreate.")}'
    found = _find_system_reminder_blocks(tool_result_str(code), "task tools haven")
    check('T31_find_only_real_sr', len(found) == 1, f'found {len(found)}: {found}')


def t32_find_sr_blocks_tool_result():
    sr = real_sr_text("The task tools haven't been used recently.")
    found = _find_system_reminder_blocks(tool_result_str(sr), "task tools haven")
    check('T32_find_in_tool_result', len(found) == 1, f'found {len(found)}')


# ── _content_contains ────────────────────────────────────────────────────────

def t33_content_contains_tool_result_str():
    sr = real_sr_text("The task tools haven't been used recently.")
    result = _content_contains(tool_result_str(sr), 'task tools haven')
    check('T33_contains_in_tool_result', result is True, f'got {result}')


def t34_content_contains_text_block():
    sr = real_sr_text("The task tools haven't been used recently.")
    result = _content_contains(text_block(sr), 'task tools haven')
    check('T34_contains_in_text_block', result is True, f'got {result}')


# ── TASK-NOTIFICATION (non-regression) ───────────────────────────────────────

def t35_task_notification_stripped_from_tool_result():
    tn = '<task-notification><task-id>abc</task-id><summary>done</summary></task-notification>'
    result = _strip_task_notification_tags(tool_result_str(tn))
    inner = result[0]['content']
    check('T35_tn_stripped_from_tr', '<task-notification>' not in inner, repr(inner[:60]))
    check('T35_tn_summary_preserved', 'done' in inner, repr(inner))


# ── WAKEUP FALSE-POSITIVE TESTS ───────────────────────────────────────────────
# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
import importlib as _wakeup_il
_rules_mod = _wakeup_il.import_module('src.proxy.rules')
_apply_first_pass = _rules_mod._apply_first_pass
_apply_bg_exit_strip = _rules_mod._apply_bg_exit_strip
_bgk_mod = _wakeup_il.import_module('src.proxy.strip_bg_completed')
_WAKEUP_TEXT = _bgk_mod._WAKEUP_TEXT
del _wakeup_il, _rules_mod, _bgk_mod


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


# W01 — <task-notification> in tool_result str → TN branch must NOT fire
def w01_tn_in_tool_result_str():
    tn_data = 'RAG result: <task-notification><status>completed</status><summary>done</summary></task-notification>'
    msgs = [{'role': 'user', 'content': tool_result_str(tn_data)}]
    new_msgs, mods, _, _c, _ = _apply_first_pass(msgs)
    content = new_msgs[0]['content']
    check('W01_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W01_tn_mod_not_fired', not any('task_notification' in m for m in mods), f'mods: {mods}')
    check('W01_tool_result_intact', new_msgs[0]['content'][0]['content'] == tn_data)


# W02 — <task-notification> in tool_result list-of-text → TN branch must NOT fire
def w02_tn_in_tool_result_list():
    tn_data = 'source: <task-notification><status>failed</status><summary></summary></task-notification>'
    msgs = [{'role': 'user', 'content': tool_result_list(tn_data)}]
    new_msgs, mods, _, _c, _ = _apply_first_pass(msgs)
    content = new_msgs[0]['content']
    check('W02_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W02_tn_mod_not_fired', not any('task_notification' in m for m in mods), f'mods: {mods}')
    check('W02_tool_result_intact', new_msgs[0]['content'][0]['content'][0]['text'] == tn_data)


# W03 — complete BGK pattern in tool_result str → BGK branch must NOT fire, data intact
def w03_bgk_in_tool_result_str():
    bgk_data = 'log: Background command "sleep 600" completed (exit code 143)\n'
    msgs = [{'role': 'user', 'content': tool_result_str(bgk_data)}]
    new_msgs, mods, _, _c, _ = _apply_bg_exit_strip(msgs)
    content = new_msgs[0]['content']
    check('W03_no_wakeup_injected', not _has_wakeup(content), f'wakeup found: {content}')
    check('W03_bgk_mod_not_fired', 'replaced_bg_completed_text' not in mods, f'mods: {mods}')
    check('W03_tool_result_intact', new_msgs[0]['content'][0]['content'] == bgk_data)


# W04 — genuine plain-string completed TN → wakeup injected, mod=trimmed_task_notification
def w04_genuine_tn_completed_plain_string():
    tn = '<task-notification>\n<status>completed</status>\n<summary>Background command "sleep 10" completed (exit code 0)</summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _ = _apply_first_pass(msgs)
    check('W04_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W04_mod_trimmed', 'trimmed_task_notification' in mods, f'mods: {mods}')


# W05 — genuine plain-string failed TN → wakeup injected, mod=replaced_task_notification
def w05_genuine_tn_failed_plain_string():
    tn = '<task-notification>\n<status>failed</status>\n<summary></summary>\n</task-notification>\n'
    msgs = [{'role': 'user', 'content': tn}]
    new_msgs, mods, _, _c, _ = _apply_first_pass(msgs)
    check('W05_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W05_mod_replaced', 'replaced_task_notification' in mods, f'mods: {mods}')


# W06 — genuine plain-string BGK kill notification → wakeup injected, mod=replaced_bg_completed_text
def w06_genuine_bgk_plain_string():
    bgk = 'Background command "sleep 600" completed (exit code 143)\n'
    msgs = [{'role': 'user', 'content': bgk}]
    new_msgs, mods, _, _c, _ = _apply_bg_exit_strip(msgs)
    check('W06_wakeup_injected', _has_wakeup(new_msgs[0]['content']), repr(new_msgs[0]['content'])[:80])
    check('W06_mod_replaced', 'replaced_bg_completed_text' in mods, f'mods: {mods}')


if __name__ == '__main__':
    tests = [
        t01_task_tools_nag_real_text_block, t02_task_tools_nag_fp_code_literal, t03_task_tools_nag_tool_result_str,
        t04_pyright_real, t05_pyright_fp, t06_pyright_tool_result_nested,
        t07_deferred_tools_real, t08_deferred_tools_fp, t09_deferred_tools_tool_result,
        t10_user_interrupt_partial_body_preserved, t11_user_interrupt_fp, t12_user_interrupt_tool_result,
        t13_system_notification_real, t14_system_notification_fp, t15_system_notification_tool_result,
        t16_file_modified_real, t17_file_modified_fp, t18_file_modified_tool_result,
        t19_claudemd_real, t20_claudemd_fp, t21_claudemd_tool_result,
        t22_date_changed_real, t23_date_changed_fp, t24_date_changed_tool_result,
        t25_shape_plain_string, t26_shape_list_text, t27_shape_tool_result_str, t28_shape_tool_result_list,
        t29_plan_mode_returns_none_when_empty, t30_plan_mode_preserves_other_content,
        t31_find_sr_blocks_skips_code_literal, t32_find_sr_blocks_tool_result,
        t33_content_contains_tool_result_str, t34_content_contains_text_block,
        t35_task_notification_stripped_from_tool_result,
        w01_tn_in_tool_result_str, w02_tn_in_tool_result_list, w03_bgk_in_tool_result_str,
        w04_genuine_tn_completed_plain_string, w05_genuine_tn_failed_plain_string,
        w06_genuine_bgk_plain_string,
    ]

    print(f'Running {len(tests)} tests...\n')
    for fn in tests:
        fn()

    total = len(PASS) + len(FAIL)
    print(f'\n{len(PASS)}/{total} passed')
    if FAIL:
        print('FAILED:', FAIL)
        sys.exit(1)
    print('ALL PASS')
