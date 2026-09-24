# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    _O, check, mk_sr, text_block, tool_result_str, tool_result_list,
    _apply_final_sr_pass, apply_modification_rules,
)

_ENV_BODY = (
    "As you answer the user's questions, you can use the following context:\n"
    "# userEmail\n"
    "The user's email address is brunowinter7934@gmail.com.\n"
    "# currentDate\n"
    "Today's date is 2026-09-24.\n\n"
    "      IMPORTANT: this context may or may not be relevant to your tasks. "
    "You should not respond to this context unless it is highly relevant to your task."
)

_ATTR_TEMPLATE = (
    "Attribution for git commits and pull requests you create from here on (this replaces Claude Code's own "
    "earlier attribution guidance, such as a previous copy of this reminder; the user's own instructions about "
    "these lines, such as a CLAUDE.md or memory rule, take precedence over this reminder, but do not add "
    "attribution lines this reminder leaves out):\n"
    "- End git commit messages with:\n"
    "Co-Authored-By: {model} <noreply@anthropic.com>\n"
    "- End pull request descriptions with:\n"
    "\U0001F916 Generated with [Claude Code](https://claude.com/claude-code)"
)

_TASK_PROMPT = "You work in the monitor-cc repo, in your own worktree.\n\n## Task\n\nDo the thing."


def _attr_sr(model='Sonnet 5'):
    return mk_sr(_ATTR_TEMPLATE.format(model=model))


def _msg0(model='Sonnet 5'):
    return [{'role': 'user', 'content': [
        {'type': 'text', 'text': mk_sr(_ENV_BODY)},
        {'type': 'text', 'text': _attr_sr(model)},
        {'type': 'text', 'text': _TASK_PROMPT},
    ]}]


# FUNCTIONS

def ga01_observed_block_stripped_env_stripped_task_untouched():
    new_msgs, mods, removed, changed, _, ops = _apply_final_sr_pass(_msg0())
    blocks = new_msgs[0]['content']
    check('GA01_attribution_block_stripped', blocks[1]['text'] == '.', repr(blocks[1]['text'])[:120])
    check('GA01_env_context_block_stripped', blocks[0]['text'] == '.', repr(blocks[0]['text'])[:120])
    check('GA01_task_prompt_untouched', blocks[2]['text'] == _TASK_PROMPT)
    check('GA01_mod_and_change_recorded', mods == ['stripped_all_sr_msg0'] and changed == [0], f'{mods} {changed}')
    check('GA01_removed_contains_attribution', any(r.startswith(_O + '\nAttribution for git commits') for r in removed[0]), repr(removed))
    check('GA01_ops_recorded', 0 in ops and bool(ops[0]), repr(ops))


def ga02_model_name_not_matched():
    new_msgs, _, _, changed, _, _ = _apply_final_sr_pass(_msg0('Opus 5.5'))
    check('GA02_opus_variant_stripped', new_msgs[0]['content'][1]['text'] == '.', repr(new_msgs[0]['content'][1]['text'])[:120])
    check('GA02_change_recorded', changed == [0])


def ga03_quoted_copy_in_tool_result_preserved():
    quoted = "Found this in the transcript:\n```\n" + _attr_sr() + "\n```\n"
    for make in (tool_result_str, tool_result_list):
        content = make(quoted)
        new_msgs, _, _, changed, _, _ = _apply_final_sr_pass([{'role': 'user', 'content': content}])
        check(f'GA03_{make.__name__}_untouched', new_msgs[0]['content'] == content)
        check(f'GA03_{make.__name__}_no_change', 0 not in changed, f'changed: {changed}')


def ga04_full_pipeline_main_and_worker_context():
    for ctx in ('', 'gapturn'):
        payload = {'system': [], 'messages': _msg0()}
        modified, mods, _, idxs, _, _, _, _ = apply_modification_rules(payload, 'opus', '', ctx)
        blocks = modified['messages'][0]['content']
        check(f'GA04_ctx_{ctx or "main"}_attribution_stripped', blocks[1]['text'] == '.', repr(blocks[1]['text'])[:120])
        check(f'GA04_ctx_{ctx or "main"}_task_prompt_untouched', blocks[2]['text'] == _TASK_PROMPT)


def ga05_mid_text_mention_preserved():
    text = "Remember: Attribution for git commits and pull requests you create is configured elsewhere."
    result = _apply_final_sr_pass([{'role': 'user', 'content': text_block(text)}])
    check('GA05_plain_mention_untouched', result[0][0]['content'][0]['text'] == text)
    sr = mk_sr("Something else entirely. Attribution for git commits and pull requests you create later.")
    result = _apply_final_sr_pass([{'role': 'user', 'content': text_block(sr)}])
    check('GA05_non_prefix_sr_untouched', result[0][0]['content'][0]['text'] == sr)
