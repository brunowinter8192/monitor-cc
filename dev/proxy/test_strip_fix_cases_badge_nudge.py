# INFRASTRUCTURE
from test_strip_fix_fixtures import check
from test_strip_fix_cases_badge import (
    _TT_MSG, _deltas_for_single_msg, _badge_for, _accumulate, _build_deltas,
    _ops_from_content_change,
)

_NUDGE_A = ("First privately list what you need next; then request every item that doesn't "
            "depend on another's result in this one response.")
_NUDGE_B = ("Only you see that command's output — the user's terminal shows at most a few lines "
            "of it. If the user needs to read any of it, put it in your reply.")


# FUNCTIONS

def tt10_nudge_prefixed_tag_badges_neither_word():
    cases = [
        ('single_a', f'{_NUDGE_A}\n\n{_TT_MSG}'),
        ('single_b', f'{_NUDGE_B}\n\n{_TT_MSG}'),
        ('combined_ab', f'{_NUDGE_A}\n\n{_NUDGE_B}\n\n{_TT_MSG}'),
        ('combined_ba', f'{_NUDGE_B}\n\n{_NUDGE_A}\n\n{_TT_MSG}'),
        ('repeated_b', f'{_NUDGE_B}\n\n{_NUDGE_B}\n\n{_TT_MSG}'),
        ('triple', f'{_NUDGE_B}\n\n{_NUDGE_A}\n\n{_NUDGE_B}\n\n{_TT_MSG}'),
    ]
    for label, body in cases:
        s, i = _deltas_for_single_msg('system', body, '.')
        show_strip, show_inject = _badge_for(s, i)
        check(f'TT10_{label}_badge_strip_false', show_strip is False, f'{label}: got {show_strip!r}')
        check(f'TT10_{label}_badge_inject_false', show_inject is False, f'{label}: got {show_inject!r}')


def tt11_nudge_mixed_with_real_content_still_badges():
    deferred = ('The following deferred tools are now available via ToolSearch. Their schemas '
                'are NOT loaded.')
    hook_msg = ('PostToolUseFailure:Bash hook additional context: This tool call FAILED. '
                '1. Diagnose why before any retry.')
    cases = [
        ('nudge_plus_deferred', f'{_NUDGE_A}\n\n{deferred}\n\n{_TT_MSG}'),
        ('deferred_plus_nudge', f'{deferred}\n\n{_NUDGE_B}\n\n{_TT_MSG}'),
        ('nudge_plus_hook_msg', f'{_NUDGE_A}\n\n{hook_msg}\n\n{_TT_MSG}'),
        ('unknown_sentence_alone', f'Some brand-new CC reminder text never seen before.\n\n{_TT_MSG}'),
        ('unknown_plus_known_nudge', f'{_NUDGE_A}\n\nSome brand-new CC reminder text.\n\n{_TT_MSG}'),
    ]
    for label, body in cases:
        s, i = _deltas_for_single_msg('system', body, '.')
        show_strip, show_inject = _badge_for(s, i)
        check(f'TT11_{label}_badge_strip_true', show_strip is True, f'{label}: got {show_strip!r}')
        check(f'TT11_{label}_badge_inject_true', show_inject is True, f'{label}: got {show_inject!r}')


def tt12_two_trailing_messages_in_one_delta_stays_quiet():
    orig = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'system', 'content': f'{_NUDGE_B}\n\n{_TT_MSG}'},
        {'role': 'system', 'content': f'{_NUDGE_A}\n\n{_NUDGE_B}\n\n{_TT_MSG}'},
    ]}
    fwd = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'system', 'content': '.'},
        {'role': 'system', 'content': '.'},
    ]}
    all_ops = {
        0: _ops_from_content_change(orig['messages'][0]['content'], '.', full_replace=True),
        1: _ops_from_content_change(orig['messages'][1]['content'], '.', full_replace=True),
    }
    s, i, _ns, _ni = _build_deltas(orig, fwd, 'rid-two-trailing', None, None, 'claude-opus-4', all_ops)
    show_strip, show_inject = _badge_for(s, i)
    check('TT12_two_nudge_messages_badge_strip_false', show_strip is False, f'got {show_strip!r}')
    check('TT12_two_nudge_messages_badge_inject_false', show_inject is False, f'got {show_inject!r}')

    nag = "<system-reminder>\nThe task tools haven't been used recently.\n</system-reminder>"
    orig3 = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'system', 'content': f'{_NUDGE_B}\n\n{_TT_MSG}'},
        {'role': 'user', 'content': nag},
    ]}
    fwd3 = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'system', 'content': '.'},
        {'role': 'user', 'content': '.'},
    ]}
    all_ops3 = {
        0: _ops_from_content_change(orig3['messages'][0]['content'], '.', full_replace=True),
        1: _ops_from_content_change(nag, '.', full_replace=True),
    }
    s3, i3, _ns3, _ni3 = _build_deltas(orig3, fwd3, 'rid-mixed-trailing', None, None, 'claude-opus-4', all_ops3)
    show_strip3, show_inject3 = _badge_for(s3, i3)
    check('TT12_nudge_plus_real_badge_strip_true', show_strip3 is True, f'got {show_strip3!r}')
    check('TT12_nudge_plus_real_badge_inject_true', show_inject3 is True, f'got {show_inject3!r}')


def tt13_lag_classifier_widens_for_nudge_shape():
    from src.proxy_display.proxy_badge import _is_total_tokens_nuke
    check('TT13_bare_tag_still_qualifies',
          _is_total_tokens_nuke({'0': [_TT_MSG]}) is True)
    check('TT13_single_nudge_qualifies',
          _is_total_tokens_nuke({'0': [f'{_NUDGE_A}\n\n{_TT_MSG}']}) is True)
    check('TT13_combined_nudges_qualify',
          _is_total_tokens_nuke({'0': [f'{_NUDGE_B}\n\n{_NUDGE_A}\n\n{_TT_MSG}']}) is True)
    check('TT13_real_content_does_not_qualify',
          _is_total_tokens_nuke({'0': ['PostToolUseFailure:Bash hook additional context: FAILED.'
                                       f'\n\n{_TT_MSG}']}) is False)
    check('TT13_two_texts_does_not_qualify',
          _is_total_tokens_nuke({'0': [_TT_MSG], '1': [_TT_MSG]}) is False)


def tt14_rendered_header_badge_words_for_nudge_class():
    import re as _re
    from src.proxy_display.render_turn import _build_req_header_line
    _ansi = _re.compile(r'\x1b\[[0-9;]*m')

    def _words(s_entry, i_entry):
        _hc_s, acc_s = _accumulate(s_entry, 'f1')
        _hc_i, acc_i = _accumulate(i_entry, 'f1')
        entry = {
            'flow_id': 'f1', 'model': 'claude-opus-4', 'message_count': 3,
            '_strip_fns_lookup': acc_s['_has_content_by_flow_id'],
            '_inject_fns_lookup': acc_i['_has_content_by_flow_id'],
            '_strip_msgs_lookup': acc_s['_msg_idx_by_flow_id'],
            '_inject_msgs_lookup': acc_i['_msg_idx_by_flow_id'],
        }
        header = _build_req_header_line(
            entry, entry_idx=0, num_label='#1', req_symbol='>', model_short='opus',
            msg_count=3, mods_str='', warn_str='', pane_width=200, copy_feedback=None,
        )
        visible = _ansi.sub('', header)
        return ' '.join(w for w in ('strip', 'inject') if _re.search(rf'\b{w}\b', visible))

    nudge_body = f'{_NUDGE_A}\n\n{_NUDGE_B}\n\n{_TT_MSG}'
    check('TT14_nudge_renders_nothing', _words(*_deltas_for_single_msg('system', nudge_body, '.')) == '',
          repr(_words(*_deltas_for_single_msg('system', nudge_body, '.'))))
    mixed_body = f'{_NUDGE_A}\n\nSome brand-new CC reminder text.\n\n{_TT_MSG}'
    check('TT14_unknown_mixed_renders_strip_inject',
          _words(*_deltas_for_single_msg('system', mixed_body, '.')) == 'strip inject',
          repr(_words(*_deltas_for_single_msg('system', mixed_body, '.'))))
