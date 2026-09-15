# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    _O, _C, check, mk_sr, real_sr_text, fp_inline, tool_result_str, tool_result_list, text_block,
    _strip_system_reminders, _strip_plan_mode_blocks, _strip_user_interrupt_sr,
    _strip_pyright_diagnostics, _content_contains, _find_system_reminder_blocks,
    _apply_first_pass, _apply_final_sr_pass,
)

# FUNCTIONS

# ── TEMPLATE TESTS ────────────────────────────────────────────────────────────

# T01-T03: task-tools-nag
def t01_task_tools_nag_real_text_block():
    sr = real_sr_text("The task tools haven't been used recently. Consider using TaskCreate.")
    result = _strip_system_reminders(text_block(sr))
    check('T01_task_nag_stripped', _O not in result[0]['text'])


def t02_task_tools_nag_fp_code_literal():
    content = fp_inline("The task tools haven't been used recently. Consider using TaskCreate.")
    # Inside tool_result, the strip no longer descends at all — the mid-line code-literal AND
    # the real trailing standalone SR are both preserved (whole block untouched).
    result = _strip_system_reminders(tool_result_str(content))
    remaining = result[0]['content']
    check('T02_nag_fp_code_preserved', 'if "' + _O + '" in text:' in remaining, repr(remaining[:80]))
    check('T02_nag_real_sr_now_preserved', remaining == content, repr(remaining[-100:]))


def t03_task_tools_nag_tool_result_preserved():
    sr = real_sr_text("The task tools haven't been used recently. Consider using TaskCreate.")
    result = _strip_system_reminders(tool_result_str(sr))
    check('T03_nag_in_tool_result_preserved', result[0]['content'] == sr)


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


def t06_pyright_tool_result_nested_preserved():
    body = '<new-diagnostics>The following new diagnostic issues were detected:\n\ntest.py: error</new-diagnostics>'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_list(sr))
    check('T06_pyright_nested_preserved', result[0]['content'][0]['text'] == sr)


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
    # Inside tool_result nothing descends — quoted string AND the real trailing SR both preserved.
    check('T08_deferred_quoted_preserved', '"The following deferred tools' in remaining)
    check('T08_deferred_real_now_preserved', remaining == code, repr(remaining[-100:]))


def t09_deferred_tools_tool_result_preserved():
    body = 'The following deferred tools are now available via ToolSearch.\nAskUserQuestion'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T09_deferred_in_tool_result_preserved', result[0]['content'] == sr)


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


def t12_user_interrupt_tool_result_preserved():
    body = 'The user sent a new message while you were working:\nstop working please\n\nIMPORTANT: Address this.'
    sr = real_sr_text(body)
    result = _strip_user_interrupt_sr(tool_result_str(sr), 'user sent a new message while you were working')
    inner = result[0]['content']
    # Partial mode (IMPORTANT-line strip) no longer applies inside tool_result either — untouched.
    check('T12_interrupt_tr_important_preserved', 'IMPORTANT:' in inner, repr(inner))
    check('T12_interrupt_tr_now_byte_exact', inner == sr, repr(inner))


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


def t15_system_notification_tool_result_preserved():
    body = '[SYSTEM NOTIFICATION - NOT USER INPUT]\nBackground task event.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T15_sysnotif_tool_result_preserved', result[0]['content'] == sr)


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
    check('T17_filemod_real_now_preserved', remaining == code, repr(remaining[-100:]))


def t18_file_modified_tool_result_preserved():
    body = 'Note: /Users/foo/DOCS.md was modified, either by the user or by a linter.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T18_filemod_tool_result_preserved', result[0]['content'] == sr)


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


def t21_claudemd_tool_result_preserved():
    body = 'Contents of /path/CLAUDE.md:\n# claudeMd\nProject overview here.'
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T21_claudemd_tool_result_preserved', result[0]['content'] == sr)


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


def t24_date_changed_tool_result_preserved():
    body = "The date has changed. Today's date is now 2026-04-22."
    sr = real_sr_text(body)
    result = _strip_system_reminders(tool_result_str(sr))
    check('T24_datechanged_tool_result_preserved', result[0]['content'] == sr)


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


def t27_shape_tool_result_str_now_preserved():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    text = f'prefix\n{sr}\nsuffix'
    result = _strip_system_reminders(tool_result_str(text))
    check('T27_tr_str_now_byte_exact', result[0]['content'] == text)


def t28_shape_tool_result_list_now_preserved():
    sr = real_sr_text("The task tools haven't been used recently. Use TaskCreate.")
    text = f'prefix\n{sr}\nsuffix'
    result = _strip_system_reminders(tool_result_list(text))
    check('T28_tr_list_now_byte_exact', result[0]['content'][0]['text'] == text)


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

def t31_find_sr_blocks_tool_result_finds_none():
    # Same real+code-literal mix as before the fix — now 0 found either way, tool_result isn't scanned.
    code = f'if "{_O}" in text:\n    pass\n\n{real_sr_text("The task tools haven\'t been used recently. Use TaskCreate.")}'
    found = _find_system_reminder_blocks(tool_result_str(code), "task tools haven")
    check('T31_find_none_in_tool_result', len(found) == 0, f'found {len(found)}: {found}')


def t32_find_sr_blocks_top_level_real_found():
    sr = real_sr_text("The task tools haven't been used recently.")
    found = _find_system_reminder_blocks(text_block(sr), "task tools haven")
    check('T32_find_real_at_top_level', len(found) == 1, f'found {len(found)}')


# ── _content_contains ────────────────────────────────────────────────────────
# _content_contains itself still descends into tool_result — it remains the correct gate for the
# out-of-scope non-SR passes (git-lock, hook-prefix, bd-noise) whose genuine content only lives
# there; the SR family switched its own call sites to _top_level_content_contains instead (see
# _apply_first_pass / _apply_cumulative_sr_strips), it did not change this shared helper.

def t33_content_contains_tool_result_str():
    sr = real_sr_text("The task tools haven't been used recently.")
    result = _content_contains(tool_result_str(sr), 'task tools haven')
    check('T33_contains_in_tool_result', result is True, f'got {result}')


def t34_content_contains_text_block():
    sr = real_sr_text("The task tools haven't been used recently.")
    result = _content_contains(text_block(sr), 'task tools haven')
    check('T34_contains_in_text_block', result is True, f'got {result}')


# ── SR-FAMILY TOOL_RESULT NON-DESCENT (2026-07-28 FP-nuke fix) ────────────────
# _apply_final_sr_pass has NO gate at all — it calls _strip_all_system_reminders unconditionally
# on every user message, so the traversal fix in strip_sr.py is the ONLY thing standing between it
# and tool_result content. These cases give it extra scrutiny: both tool_result shapes must be
# untouched, and the block object must come back by IDENTITY (not a rebuilt-but-equal dict), since
# a rebuild would still register as a change in the diff-based bookkeeping downstream.

def t35_final_sr_pass_tool_result_str_identity_preserved():
    sr = real_sr_text('[SYSTEM NOTIFICATION - NOT USER INPUT]\nBackground task event.')
    content = tool_result_str(sr)
    msgs = [{'role': 'user', 'content': content}]
    new_msgs, mods, _, changed, _, _ops = _apply_final_sr_pass(msgs)
    check('T35_final_sr_pass_tool_result_str_untouched', new_msgs[0]['content'] == content)
    check('T35_final_sr_pass_block_identity', new_msgs[0]['content'][0] is content[0])
    check('T35_final_sr_pass_no_change_recorded', 0 not in changed, f'changed: {changed}')


def t36_final_sr_pass_tool_result_list_identity_preserved():
    sr = real_sr_text('[SYSTEM NOTIFICATION - NOT USER INPUT]\nBackground task event.')
    content = tool_result_list(sr)
    msgs = [{'role': 'user', 'content': content}]
    new_msgs, mods, _, changed, _, _ops = _apply_final_sr_pass(msgs)
    check('T36_final_sr_pass_tool_result_list_untouched', new_msgs[0]['content'] == content)
    check('T36_final_sr_pass_block_identity', new_msgs[0]['content'][0] is content[0])
    check('T36_final_sr_pass_no_change_recorded', 0 not in changed, f'changed: {changed}')


# T37 — real Occurrence-8 shape: a rag-cli/process-docs excerpt fencing a literal env-context
# system-reminder as a documentation example, inside a tool_result — must survive byte-exact.
def t37_occurrence8_fenced_env_context_in_tool_result_preserved():
    env_sr = (
        f'{_O}\n'
        "As you answer the user's questions, you can use the following context:\n"
        "# userEmail\nThe user's email address is brunowinter7934@gmail.com.\n"
        "# currentDate\nToday's date is 2026-05-30.\n\n"
        "      IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task.\n"
        f'{_C}\n'
    )
    doc_excerpt = (
        "## Task B — Env-context system-reminder (userEmail / currentDate)\n\n"
        "### What we stripped\n\n"
        "CC injects this SR block on nearly every request:\n```\n"
        f"{env_sr}"
        "```\n334 chars of inner text per request, never useful to the proxy model.\n"
    )
    content = tool_result_str(doc_excerpt)
    msgs = [{'role': 'user', 'content': content}]
    new_msgs, mods, _, changed, _, _ops = _apply_final_sr_pass(msgs)
    check('T37_occ8_fenced_env_context_untouched', new_msgs[0]['content'] == content)
    check('T37_occ8_block_identity', new_msgs[0]['content'][0] is content[0])
    check('T37_occ8_no_change_recorded', 0 not in changed, f'changed: {changed}')


# T38/T39 — top-level SR stripping still works: this is a SCOPE REDUCTION, not a disable. One
# template from an _apply_first_pass gated branch, one only _apply_final_sr_pass's catch-all covers.
def t38_top_level_task_tools_nag_still_stripped_via_first_pass():
    sr = real_sr_text("The task tools haven't been used recently. Consider using TaskCreate.")
    msgs = [{'role': 'user', 'content': sr}]
    new_msgs, mods, _, _c, _, _ops = _apply_first_pass(msgs)
    check('T38_top_level_nag_stripped', _O not in new_msgs[0]['content'])
    check('T38_top_level_nag_mod_fired', 'stripped_task_tools_nag' in mods, f'mods: {mods}')


def t39_top_level_date_changed_still_stripped_via_final_sr_pass():
    sr = real_sr_text("The date has changed. Today's date is now 2026-04-22.")
    msgs = [{'role': 'user', 'content': sr}]
    new_msgs, mods, _, _c, _, _ops = _apply_final_sr_pass(msgs)
    check('T39_top_level_datechanged_stripped', _O not in new_msgs[0]['content'])
    check('T39_top_level_datechanged_mod_fired', 'stripped_all_sr_msg0' in mods, f'mods: {mods}')
