# INFRASTRUCTURE
import importlib
import json
import tempfile
from pathlib import Path

from test_strip_fix_fixtures import check, tool_result_str

_sid_mod = importlib.import_module('src.proxy.strip_inject_delta')
_build_deltas = _sid_mod._build_stripped_injected_deltas
_ro_mod = importlib.import_module('src.proxy.rule_ops')
_ops_from_content_change = _ro_mod._ops_from_content_change

# FUNCTIONS

# ── TOTAL_TOKENS BADGE-SUPPRESSION TESTS (parser.py read-side, 2026-08-29) ────
# Newer CC appends a fresh role='system' '<total_tokens>N tokens left</total_tokens>' message to the
# END of the history on every request. _apply_role_system_strip nukes it to '.' (correct, unchanged),
# and the delta WRITER records that nuke normally (also unchanged — the expanded view must keep
# rendering the olive stripped text + green '.' at that message). The nuke lands on a NEW message
# index each request, so its loc_key is new each request and the writer's hash dedup structurally
# cannot suppress it — which made the REQ-header badge light up on virtually every request.
# Fix location is READ-SIDE ONLY: parser.accumulate_dual_log's has_content computation, via
# _msgs_delta_is_substantial. Two classes stop counting toward the badge:
#   - stripped: a message whose blocks' stripped texts are exactly ONE text full-matching the marker
#   - injected: a block whose injected spans are only '.', the API-required empty-block filler
# Overlay section dicts and _msg_idx_by_flow_id are deliberately NOT filtered, so span rendering and
# per-flow scoping are byte-identical to before. These tests drive the real
# _build_stripped_injected_deltas (with real ops from _ops_from_content_change) into the real
# accumulate_dual_log — the production write path feeding the production read path.

_TT_MSG = '<total_tokens>14979724 tokens left</total_tokens>'


# Build (stripped_entry, injected_entry) for a single-message payload nuked to `new_content`,
# with ops recorded exactly as the production passes record them (full_replace for a '.' nuke).
def _deltas_for_single_msg(role: str, old_content, new_content, full_replace: bool = True) -> tuple:
    orig = {'model': 'claude-opus-4', 'system': [], 'tools': [],
            'messages': [{'role': role, 'content': old_content}]}
    fwd = {'model': 'claude-opus-4', 'system': [], 'tools': [],
           'messages': [{'role': role, 'content': new_content}]}
    all_ops = {0: _ops_from_content_change(old_content, new_content, full_replace=full_replace)}
    s_entry, i_entry, _new_s, _new_i = _build_deltas(
        orig, fwd, 'rid-test', None, None, 'claude-opus-4', all_ops,
    )
    return s_entry, i_entry


# Resolve the REQ-header badge pair the way the pane does: accumulate BOTH dual-log lines of one
# flow through the real accumulate_dual_log, attach the four per-flow lookups exactly as
# pane.py does, then ask the real parser.badge_flags. Returns (show_strip, show_inject).
def _badge_for(s_entry: dict, i_entry: dict, flow_id: str = 'f1') -> tuple:
    from src.proxy_display.proxy_badge import badge_flags
    _hc_s, acc_s = _accumulate(s_entry, flow_id)
    _hc_i, acc_i = _accumulate(i_entry, flow_id)
    entry = {
        'flow_id': flow_id,
        '_strip_fns_lookup': acc_s['_has_content_by_flow_id'],
        '_inject_fns_lookup': acc_i['_has_content_by_flow_id'],
        '_strip_msgs_lookup': acc_s['_msg_idx_by_flow_id'],
        '_inject_msgs_lookup': acc_i['_msg_idx_by_flow_id'],
    }
    return badge_flags(entry)


# Run one delta entry through the REAL accumulate_dual_log; returns (has_content, acc_for_family)
def _accumulate(entry: dict, flow_id: str = 'f1') -> tuple:
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log
    entry = {**entry, 'flow_id': flow_id}
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(entry) + '\n')
        tmp = Path(f.name)
    acc: dict = {}
    try:
        accumulate_dual_log(tmp, 0, acc)
    finally:
        tmp.unlink()
    fam = acc.get('opus', {})
    return fam.get('_has_content_by_flow_id', {}).get(flow_id), fam


# TT01 — the WRITER is unchanged: the class still produces full delta entries with spans, so the
# expanded view keeps rendering the olive stripped text and the green '.' filler.
def tt01_total_tokens_still_written_with_spans():
    s, i = _deltas_for_single_msg('system', _TT_MSG, '.')
    check('TT01_stripped_spans_written', s['messages_delta'] == {'0': {'0': [_TT_MSG]}}, repr(s['messages_delta']))
    inj = i['messages_delta'].get('0', {}).get('0')
    check('TT01_injected_spans_written', inj is not None, repr(i['messages_delta']))
    check('TT01_injected_span_is_dot_filler', any(tag == 'injected' and t == '.' for tag, t in (inj or [])), repr(inj))
    check('TT01_rs_attribution_kept', s['fn_map'] == {'msg.0.0': '_apply_role_system_strip'}, repr(s['fn_map']))


# TT02 — the BADGE goes quiet on both sides, and the overlay/scoping data survives untouched
def tt02_total_tokens_badge_false_but_overlay_intact():
    s, i = _deltas_for_single_msg('system', _TT_MSG, '.')
    hc_s, acc_s = _accumulate(s)
    hc_i, acc_i = _accumulate(i)
    check('TT02_stripped_signal_false', hc_s is False, f'got {hc_s!r}')
    check('TT02_injected_signal_false', hc_i is False, f'got {hc_i!r}')
    # the badge the header actually renders — BOTH words stay off for this class
    show_strip, show_inject = _badge_for(s, i)
    check('TT02_badge_strip_off', show_strip is False, f'got {show_strip!r}')
    check('TT02_badge_inject_off', show_inject is False, f'got {show_inject!r}')
    # overlay + per-flow msg scoping must be EXACTLY as before — spans still render
    check('TT02_stripped_overlay_kept', acc_s['messages'] == {'0': {'0': [_TT_MSG]}}, repr(acc_s['messages']))
    check('TT02_injected_overlay_kept', acc_i['messages'].get('0', {}).get('0') is not None, repr(acc_i['messages']))
    check('TT02_msg_idx_tracked', acc_s['_msg_idx_by_flow_id']['f1'] == {'0'}, repr(acc_s['_msg_idx_by_flow_id']))
    check('TT02_msg_idx_tracked_injected', acc_i['_msg_idx_by_flow_id']['f1'] == {'0'}, repr(acc_i['_msg_idx_by_flow_id']))


# TT03 — every OTHER '.'-nuke keeps the one-to-one behavior: `strip inject`. Its '.' IS injected and
# DOES render as a green span, so the header must say so. Only the total_tokens class goes silent.
# The inject word here comes from the flow coordination in parser.badge_flags — the injected line
# alone carries just '.', indistinguishable from the total_tokens one.
def tt03_other_nukes_badge_strip_and_inject():
    cases = [
        ('nag', "<system-reminder>\nThe task tools haven't been used recently.\n</system-reminder>"),
        ('deferred', '<system-reminder>\nThe following deferred tools are now available via ToolSearch.\n</system-reminder>'),
        ('date', "<system-reminder>\nThe date has changed. Today's date is now 2026-04-22.\n</system-reminder>"),
        ('midconv', 'Some mid-conversation notice from Claude Code.'),
    ]
    for label, body in cases:
        s, i = _deltas_for_single_msg('system', body, '.')
        show_strip, show_inject = _badge_for(s, i)
        check(f'TT03_{label}_badge_strip_true', show_strip is True, f'{label}: got {show_strip!r}')
        check(f'TT03_{label}_badge_inject_true', show_inject is True, f'{label}: got {show_inject!r}')


# TT04 — a REAL content injection still badges inject (the bg-exit wake-up replacement, the case
# the badge exists for). Guards that the '.'-filler rule did not swallow genuine injections.
def tt04_real_injection_still_badges():
    bgk = 'Background command "sleep 600" completed (exit code 143)\n'
    wake = 'background done — check worker or other process\n'
    s, i = _deltas_for_single_msg('user', bgk, wake, full_replace=False)
    hc_i, _ = _accumulate(i)
    check('TT04_real_injection_signal_true', hc_i is True, f'got {hc_i!r}')
    show_strip, show_inject = _badge_for(s, i)
    check('TT04_badge_strip_true', show_strip is True, f'got {show_strip!r}')
    check('TT04_badge_inject_true', show_inject is True, f'got {show_inject!r}')


# TT05 — FP guard: the marker QUOTED alongside other content keeps badging. This is the shape a
# real conversation produces (the marker inside a tool_result / a longer message), as opposed to a
# bare marker-only message. Read-side has no role field, so this text-shape guard is what carries
# the anti-FP property here.
def tt05_marker_with_surrounding_content_still_badges():
    old = tool_result_str(f'log line:\n{_TT_MSG}\nend')
    s, i = _deltas_for_single_msg('user', old, tool_result_str('.'))
    show_strip, show_inject = _badge_for(s, i)
    check('TT05_tool_result_badge_strip_true', show_strip is True, f'got {show_strip!r}')
    check('TT05_tool_result_badge_inject_true', show_inject is True, f'got {show_inject!r}')
    s2, i2 = _deltas_for_single_msg('user', f'note: {_TT_MSG} was logged', '.')
    show_strip2, show_inject2 = _badge_for(s2, i2)
    check('TT05_inline_quote_badge_strip_true', show_strip2 is True, f'got {show_strip2!r}')
    check('TT05_inline_quote_badge_inject_true', show_inject2 is True, f'got {show_inject2!r}')


# TT06 — anchoring near-misses still badge: only the EXACT whole-text marker is suppressed
def tt06_anchoring_near_misses_still_badge():
    near = [
        ('prefix', f'note: {_TT_MSG}'),
        ('suffix', f'{_TT_MSG} and more text'),
        ('no_digits', '<total_tokens>many tokens left</total_tokens>'),
        ('wrong_wording', '<total_tokens>123 tokens remaining</total_tokens>'),
    ]
    for label, body in near:
        s, i = _deltas_for_single_msg('system', body, '.')
        show_strip, show_inject = _badge_for(s, i)
        check(f'TT06_{label}_badge_strip_true', show_strip is True, f'{label}: got {show_strip!r}')
        check(f'TT06_{label}_badge_inject_true', show_inject is True, f'{label}: got {show_inject!r}')
    s2, i2 = _deltas_for_single_msg('system', f'\n  {_TT_MSG}  \n', '.')
    show_strip2, show_inject2 = _badge_for(s2, i2)
    check('TT06_whitespace_padded_badge_strip_false', show_strip2 is False, f'got {show_strip2!r}')
    check('TT06_whitespace_padded_badge_inject_false', show_inject2 is False, f'got {show_inject2!r}')


# TT07 — mixed request: a total_tokens nuke AND a real strip in the SAME request must still badge.
# The suppression is per-MESSAGE on the stripped side, so the real strip at its own index survives
# the filter (3 such requests exist in the 1788011077 session).
def tt07_mixed_request_still_badges():
    nag = "<system-reminder>\nThe task tools haven't been used recently.\n</system-reminder>"
    orig = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'user', 'content': nag},
        {'role': 'system', 'content': _TT_MSG},
    ]}
    fwd = {'model': 'claude-opus-4', 'system': [], 'tools': [], 'messages': [
        {'role': 'user', 'content': '.'},
        {'role': 'system', 'content': '.'},
    ]}
    all_ops = {
        0: _ops_from_content_change(nag, '.', full_replace=True),
        1: _ops_from_content_change(_TT_MSG, '.', full_replace=True),
    }
    s, i, _ns, _ni = _build_deltas(orig, fwd, 'rid-mixed', None, None, 'claude-opus-4', all_ops)
    hc, acc = _accumulate(s)
    show_strip, show_inject = _badge_for(s, i)
    check('TT07_mixed_badge_strip_true', show_strip is True, f'got {show_strip!r}')
    check('TT07_mixed_badge_inject_true', show_inject is True, f'got {show_inject!r}')
    check('TT07_both_msgs_still_in_overlay', set(acc['messages'].keys()) == {'0', '1'}, repr(acc['messages']))
    check('TT07_both_msgs_in_scope', acc['_msg_idx_by_flow_id']['f1'] == {'0', '1'}, repr(acc['_msg_idx_by_flow_id']))


# TT08 — sections other than messages are untouched by the filter: a system-only or tools-only
# delta still badges, and a fields-only delta still does not (unchanged pre-existing behavior).
def tt08_other_sections_unaffected():
    base = {'type': 'stripped_delta', 'request_id': 'r', 'timestamp': 't', 'model': 'claude-opus-4',
            'is_first': False, 'counts': {}, 'system_delta': {}, 'tools_delta': {},
            'messages_delta': {}, 'fields_delta': {}, 'fn_map': {}}
    hc_sys, _ = _accumulate({**base, 'system_delta': {'2': ['some stripped rules text']}})
    check('TT08_system_delta_badges', hc_sys is True, f'got {hc_sys!r}')
    hc_tools, _ = _accumulate({**base, 'tools_delta': {'Bash': {'whole': True}}})
    check('TT08_tools_delta_badges', hc_tools is True, f'got {hc_tools!r}')
    hc_fields, _ = _accumulate({**base, 'fields_delta': {'max_tokens': '999'}})
    check('TT08_fields_delta_does_not_badge', hc_fields is False, f'got {hc_fields!r}')
    hc_tt_plus_sys, _ = _accumulate({**base, 'system_delta': {'2': ['x']},
                                     'messages_delta': {'0': {'0': [_TT_MSG]}}})
    check('TT08_tt_plus_system_badges', hc_tt_plus_sys is True, f'got {hc_tt_plus_sys!r}')


# TT09 — end-to-end through the REAL header renderer: the rendered badge words themselves. Covers
# the live-observed case (a task-tools nag nuke rendering only `strip` when it must render
# `strip inject`) and its counterpart (a total_tokens nuke rendering neither word).
def tt09_rendered_header_badge_words():
    import re as _re
    from src.proxy_display.render_turn import _build_req_header_line
    _ansi = _re.compile(r'\x1b\[[0-9;]*m')

    def _words(s_entry, i_entry):
        from src.proxy_display.proxy_badge import badge_flags  # noqa: F401 (same path badge_flags takes)
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

    nag = "<system-reminder>\nThe task tools haven't been used recently.\n</system-reminder>"
    check('TT09_nag_renders_strip_inject', _words(*_deltas_for_single_msg('system', nag, '.')) == 'strip inject',
          repr(_words(*_deltas_for_single_msg('system', nag, '.'))))
    check('TT09_total_tokens_renders_nothing', _words(*_deltas_for_single_msg('system', _TT_MSG, '.')) == '',
          repr(_words(*_deltas_for_single_msg('system', _TT_MSG, '.'))))
    bgk = 'Background command "sleep 600" completed (exit code 143)\n'
    wake = 'background done — check worker or other process\n'
    check('TT09_real_injection_renders_strip_inject',
          _words(*_deltas_for_single_msg('user', bgk, wake, full_replace=False)) == 'strip inject',
          repr(_words(*_deltas_for_single_msg('user', bgk, wake, full_replace=False))))
