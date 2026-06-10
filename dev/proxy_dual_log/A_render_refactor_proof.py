"""
Render refactor proof harness: byte-identical differential test for proxy_display render cluster.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/A_render_refactor_proof.py --mode capture
    ./venv/bin/python dev/proxy_dual_log/A_render_refactor_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- run all 14 cases, write (ansi_string, total_lines) to baseline JSON
    verify   -- run all 14 cases, assert byte-identical against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: format_proxy_block(entries, expand_states, ...) — exercises all 5 targets
transitively: render_messages, _render_entry_lines, render_tools, render_turn_expanded,
format_proxy_block itself.
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

_HERE = Path(__file__).parent
_REPORTS = _HERE / 'A_render_refactor_proof_reports'

# ORCHESTRATOR

def main():
    args = _parse_args()
    cases = _build_cases()
    if args.mode == 'capture':
        _run_capture(cases, args.output)
    else:
        sys.exit(_run_verify(cases, args.baseline))


# FUNCTIONS

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['capture', 'verify'], required=True)
    today = datetime.now().strftime('%Y%m%d')
    p.add_argument('--output', default=str(_REPORTS / f'baseline_{today}.json'))
    p.add_argument('--baseline', default=None, help='Path to baseline JSON (verify mode)')
    return p.parse_args()


def _run_capture(cases, output):
    from src.proxy_display.format import format_proxy_block
    _REPORTS.mkdir(exist_ok=True)
    results = {}
    for case in cases:
        ansi, total_lines = _render_case(case, format_proxy_block)
        results[case['name']] = {'ansi': ansi, 'total_lines': total_lines}
        print(f'  captured: {case["name"]}')
    Path(output).write_text(json.dumps(results, indent=2))
    print(f'Baseline written: {output}')


def _run_verify(cases, baseline_path):
    from src.proxy_display.format import format_proxy_block
    if not baseline_path:
        baselines = sorted(_REPORTS.glob('baseline_*.json'))
        if not baselines:
            print('ERROR: no baseline — run --mode capture first')
            return 1
        baseline_path = str(baselines[-1])
        print(f'Using baseline: {baseline_path}')
    baseline = json.loads(Path(baseline_path).read_text())
    failures = []
    for case in cases:
        name = case['name']
        ansi, total_lines = _render_case(case, format_proxy_block)
        exp = baseline.get(name)
        if exp is None:
            failures.append(f'{name}: missing from baseline')
            continue
        if ansi != exp['ansi'] or total_lines != exp['total_lines']:
            failures.append(f'{name}: MISMATCH  lines:{exp["total_lines"]}→{total_lines}  ansi_eq:{ansi==exp["ansi"]}')
    for f in failures:
        print(f'FAIL: {f}')
    if not failures:
        print(f'OK: {len(cases)} cases byte-identical')
        return 0
    return 1


def _render_case(case, format_proxy_block):
    name = case['name']
    entries = case['entries']
    expand_states = dict(case.get('expand_states', {}))
    kw = {'pane_height': 200, 'pane_width': 120}
    kw.update(case.get('kwargs', {}))
    if 'copy_rows_out' in kw:
        kw['copy_rows_out'] = set()
    if name == 'expand_fixpoint':
        return _render_fixpoint(entries, kw, format_proxy_block)
    line_map = {}
    return format_proxy_block(entries, expand_states, line_map=line_map, **kw)


def _render_fixpoint(entries, kw, format_proxy_block):
    # Iterates: render → expand all visible keys → repeat until line_map stable (fixpoint)
    expand_states = {}
    known_keys = set()
    result = ('', 0)
    for _ in range(20):
        line_map = {}
        result = format_proxy_block(entries, expand_states, line_map=line_map, **kw)
        new_keys = {v for v in line_map.values() if v is not None} - known_keys
        if not new_keys:
            break
        known_keys |= new_keys
        for key in new_keys:
            expand_states[key] = True
    return result


# ── entry / message / block builders ──────────────────────────────────────

def _mk_entry(model='claude-3-opus-20240229', msg_count=1, msgs=None, **kw):
    e = {
        'model': model,
        'message_count': msg_count,
        'messages': msgs or [],
        'system_total_chars': 200,
        'tools_total_chars': 100,
        'messages_total_chars': sum(m.get('chars', 0) for m in (msgs or [])),
        'tools_count': 0, 'tools_names': [], 'tools_defs': [], 'tools_hash': '',
        'timestamp': '2024-01-01T00:00:00',
    }
    e.update(kw)
    return e


def _mk_msg(role='user', chars=50, blocks=None, **kw):
    m = {'role': role, 'type': 'text', 'chars': chars}
    if blocks is not None:
        m['blocks'] = blocks
    m.update(kw)
    return m


def _mk_blk(btype='text', chars=50, full_text='sample text\nline 2', **kw):
    b = {'type': btype, 'chars': chars}
    if btype == 'thinking':
        b['sig_chars'] = kw.pop('sig_chars', 8)
    else:
        b['full_text'] = full_text
    b.update(kw)
    return b


# ── test cases ────────────────────────────────────────────────────────────

def _build_cases():
    return [
        _case_branch1_basic(),
        _case_branch1_stripped(),
        _case_branch2_basic(),
        _case_branch2_removed(),
        _case_dual_new_format(),
        _case_dual_legacy(),
        _case_tools_first_request(),
        _case_tools_changed(),
        _case_system_blocks(),
        _case_standalone_haiku(),
        _case_copy_feedback_on(),
        _case_hover_and_scroll(),
        _case_collision(),
        _case_expand_fixpoint(),
    ]


# Branch 1: new messages, no dual, two blocks including thinking
def _case_branch1_basic():
    msgs = [
        _mk_msg('user', 50, [_mk_blk('text', 50, 'Hello world')]),
        _mk_msg('asst', 80, [_mk_blk('text', 60, 'Response\nLine 2'), _mk_blk('thinking', 20, sig_chars=5)]),
    ]
    return {
        'name': 'branch1_basic',
        'entries': [_mk_entry(msg_count=2, msgs=msgs, diff_from_prev={'first_diff_index': 0, 'messages_added': 2})],
        'expand_states': {('req', 0): True},
    }


# Branch 1: stripped messages — EFF path (removed_chunks present) + IDX path (originals only)
def _case_branch1_stripped():
    msgs = [
        _mk_msg('user', 50, [_mk_blk()]),
        _mk_msg('asst', 60, [_mk_blk()]),   # stripped idx=1: EFF path
        _mk_msg('user', 70, [_mk_blk()]),   # stripped idx=2: IDX path
        _mk_msg('asst', 80, [_mk_blk()]),
    ]
    entry = _mk_entry(
        msg_count=4, msgs=msgs,
        diff_from_prev={'first_diff_index': 0, 'messages_added': 4},
        stripped_msg_indices=[1, 2],
        stripped_msg_removed={'1': ['original chunk\nwith content', 'second chunk']},
        stripped_msg_originals={'2': 'original text line 1\nline 2'},
    )
    return {'name': 'branch1_stripped', 'entries': [entry], 'expand_states': {('req', 0): True}}


# Branch 2: content_tail fallback (no blocks, modified message with tail)
def _case_branch2_basic():
    msgs0 = [_mk_msg('user', 50, [_mk_blk()]), _mk_msg('asst', 80, [], content_tail='old tail')]
    msgs1 = [_mk_msg('user', 50, [_mk_blk()]), _mk_msg('asst', 90, [], content_tail='updated tail\nmore content')]
    e0 = _mk_entry(msg_count=2, msgs=msgs0, tools_hash='abc')
    e1 = _mk_entry(msg_count=2, msgs=msgs1, tools_hash='abc',
                   diff_from_prev={'first_diff_index': 1, 'messages_added': 0})
    return {'name': 'branch2_basic', 'entries': [e0, e1], 'expand_states': {('req', 1): True}}


# Branch 2: removed_from_prev tail (prev has more messages)
def _case_branch2_removed():
    msgs0 = [_mk_msg('user', 50, [_mk_blk()]), _mk_msg('asst', 80, [_mk_blk()]), _mk_msg('user', 60, [_mk_blk()])]
    msgs1 = [_mk_msg('user', 50, [_mk_blk()]), _mk_msg('asst', 85, [_mk_blk()])]
    e0 = _mk_entry(msg_count=3, msgs=msgs0, tools_hash='h1')
    e1 = _mk_entry(msg_count=2, msgs=msgs1, tools_hash='h1',
                   diff_from_prev={'first_diff_index': 1, 'messages_added': 0})
    return {'name': 'branch2_removed', 'entries': [e0, e1], 'expand_states': {('req', 1): True}}


# Dual spans new-format: i_blk as list of (tag, text) tuples; s_blk as plain strings
def _case_dual_new_format():
    msgs0 = [_mk_msg('user', 100, [_mk_blk('text', 100, 'user text')])]
    msgs1 = [_mk_msg('user', 120, [_mk_blk('text', 120, 'user text modified')])]
    e0 = _mk_entry(msg_count=1, msgs=msgs0, tools_hash='h1')
    e1 = _mk_entry(
        msg_count=1, msgs=msgs1, tools_hash='h1',
        diff_from_prev={'first_diff_index': 0, 'messages_added': 0},
        _stripped_spans={'messages': {'0': {'0': ['stripped portion']}}, 'system': {}, 'tools': {}, 'fields': {}},
        _injected_spans={'messages': {'0': {'0': [('equal', 'user text'), ('injected', ' modified')]}}, 'system': {}, 'tools': {}, 'fields': {}},
    )
    return {'name': 'dual_new_format', 'entries': [e0, e1], 'expand_states': {('req', 1): True}}


# Dual spans legacy: i_blk as plain strings; s_blk as plain strings
def _case_dual_legacy():
    msgs0 = [_mk_msg('user', 100, [_mk_blk('text', 100, 'original text')])]
    msgs1 = [_mk_msg('user', 130, [_mk_blk('text', 130, 'original text injected')])]
    e0 = _mk_entry(msg_count=1, msgs=msgs0, tools_hash='h2')
    e1 = _mk_entry(
        msg_count=1, msgs=msgs1, tools_hash='h2',
        diff_from_prev={'first_diff_index': 0, 'messages_added': 0},
        _stripped_spans={'messages': {'0': {'0': ['stripped old']}}, 'system': {}, 'tools': {}, 'fields': {}},
        _injected_spans={'messages': {'0': {'0': ['injected new content']}}, 'system': {}, 'tools': {}, 'fields': {}},
    )
    return {'name': 'dual_legacy', 'entries': [e0, e1], 'expand_states': {('req', 1): True}}


# Tools section: first request (prev has no tools_hash) — tool header + desc + schema
def _case_tools_first_request():
    tool = {
        'name': 'bash', 'description': 'Run bash commands\nIn a subprocess',
        'input_schema': {'type': 'object',
                         'properties': {'command': {'type': 'string', 'description': 'The bash command'},
                                        'timeout': {'type': 'integer'}},
                         'required': ['command']},
    }
    entry = _mk_entry(msg_count=1, msgs=[_mk_msg()],
                      tools_count=1, tools_names=['bash'], tools_defs=[tool],
                      tools_hash='toolhash1', tools_total_chars=500)
    return {
        'name': 'tools_first_request',
        'entries': [entry],
        'expand_states': {('req', 0): True, ('tools', 0): True, ('tool', 0, 0): True},
    }


# Tools section: tools changed (added 'python', removed 'bash')
def _case_tools_changed():
    tool_old = {'name': 'bash', 'description': 'Run bash', 'input_schema': {}}
    tool_new = {'name': 'python', 'description': 'Run python\nScripts',
                'input_schema': {'properties': {'code': {'type': 'string', 'description': 'Python code'}}, 'required': ['code']}}
    e0 = _mk_entry(msg_count=1, msgs=[_mk_msg()],
                   tools_count=1, tools_names=['bash'], tools_defs=[tool_old],
                   tools_hash='oldhash', tools_total_chars=200)
    e1 = _mk_entry(msg_count=2, msgs=[_mk_msg(), _mk_msg('asst')],
                   tools_count=1, tools_names=['python'], tools_defs=[tool_new],
                   tools_hash='newhash', tools_total_chars=220,
                   diff_from_prev={'first_diff_index': 1, 'messages_added': 1})
    return {
        'name': 'tools_changed',
        'entries': [e0, e1],
        'expand_states': {('req', 1): True, ('tools', 1): True, ('tool', 1, 0): True},
    }


# System blocks section: two blocks, both expanded
def _case_system_blocks():
    sys_blocks = [
        {'idx': 0, 'chars': 300, 'preview': 'System prompt line 1\nLine 2'},
        {'idx': 1, 'chars': 100, 'preview': 'Second block content'},
    ]
    entry = _mk_entry(msg_count=1, msgs=[_mk_msg()], system_blocks=sys_blocks, system_total_chars=400)
    return {
        'name': 'system_blocks',
        'entries': [entry],
        'expand_states': {('req', 0): True, ('sys', 0): True, ('sys_block', 0, 0): True, ('sys_block', 0, 1): True},
    }


# Standalone haiku entry (is_standalone_entry = True, num_label = 'H')
def _case_standalone_haiku():
    entry = _mk_entry(model='claude-3-haiku-20240307', msg_count=1, msgs=[_mk_msg()],
                      system_total_chars=50, tools_total_chars=30)
    return {'name': 'standalone_haiku', 'entries': [entry], 'expand_states': {}}


# copy_feedback ON: frozen future timestamp → always shows '✓' flash
def _case_copy_feedback_on():
    entry = _mk_entry(msg_count=1, msgs=[_mk_msg('user', 50, [_mk_blk()])])
    return {
        'name': 'copy_feedback_on',
        'entries': [entry],
        'expand_states': {},
        'kwargs': {'copy_feedback': {0: 9_999_999_999.0}},
    }


# hover_row + scroll_offset: smaller pane forces scrolling, row 2 is hovered
def _case_hover_and_scroll():
    entries = [_mk_entry(msg_count=1, msgs=[_mk_msg()]) for _ in range(4)]
    return {
        'name': 'hover_and_scroll',
        'entries': entries,
        'expand_states': {},
        'kwargs': {'pane_height': 4, 'hover_row': 2, 'scroll_offset': 1},
    }


# Collision: two turn groups both produce label '#0.1' → COLLISION_BG path
def _case_collision():
    turns = [{'timestamp': '2024-01-01T00:00:00'}, {'timestamp': '2024-01-01T01:00:00'}]
    e0 = _mk_entry(msg_count=1, msgs=[_mk_msg()],
                   diff_from_prev={'messages_added': 0, 'first_diff_index': 0},
                   timestamp='2024-01-01T00:30:00')
    e1 = _mk_entry(msg_count=1, msgs=[_mk_msg()],
                   diff_from_prev={'messages_added': 0, 'first_diff_index': 0},
                   timestamp='2024-01-01T01:30:00')
    return {'name': 'collision', 'entries': [e0, e1], 'expand_states': {}, 'kwargs': {'turns': turns}}


# Expand-ALL fixpoint: kitchen-sink two entries, iterated until stable
def _case_expand_fixpoint():
    tool0 = {'name': 'read_file', 'description': 'Read a file\nFrom disk',
             'input_schema': {'properties': {'path': {'type': 'string', 'description': 'File path'}}, 'required': ['path']}}
    e0 = _mk_entry(
        msg_count=1,
        msgs=[_mk_msg('user', 80, [_mk_blk('text', 80, 'What is the capital of France?')])],
        system_blocks=[{'idx': 0, 'chars': 200, 'preview': 'You are a helpful assistant.\nBe concise.'}],
        system_total_chars=200,
        tools_count=1, tools_names=['read_file'], tools_defs=[tool0], tools_hash='hash_a',
        tools_total_chars=300, messages_total_chars=80,
        anthropic_beta=['computer-use-2024-10-22'],
        context_management={'edits': [{'type': 'truncate_messages'}]},
    )
    tool1 = {'name': 'write_file', 'description': 'Write a file',
             'input_schema': {'properties': {'path': {'type': 'string'},
                                             'content': {'type': 'string', 'description': 'File content'}},
                              'required': ['path', 'content']}}
    msgs1 = [
        _mk_msg('user', 80, [_mk_blk('text', 80, 'What is the capital of France?')]),
        _mk_msg('asst', 50, [_mk_blk('text', 40, 'Paris.'), _mk_blk('thinking', 10, sig_chars=3)]),
        _mk_msg('user', 90, [_mk_blk('text', 90, 'And Germany?')]),
    ]
    e1 = _mk_entry(
        msg_count=3, msgs=msgs1,
        system_blocks=[
            {'idx': 0, 'chars': 220, 'preview': 'You are a helpful assistant.\nBe concise and accurate.'},
            {'idx': 2, 'chars': 80,  'preview': 'Additional context block'},
        ],
        system_total_chars=300,
        tools_count=1, tools_names=['write_file'], tools_defs=[tool1], tools_hash='hash_b',
        tools_total_chars=350, messages_total_chars=220,
        diff_from_prev={'first_diff_index': 1, 'messages_added': 2},
        _stripped_spans={
            'messages': {'1': {'0': ['old response text']}},
            'system':   {'0': ['old system line']},
            'tools':    {'read_file': {'whole': True}},
            'fields':   {'max_tokens': '4096'},
        },
        _injected_spans={
            'messages': {'1': {'0': [('equal', 'Par'), ('injected', 'is.')]}},
            'system':   {'0': [('equal', 'You are a helpful assistant.\nBe concise'), ('injected', ' and accurate.')]},
            'tools':    {'write_file': {'whole': True, 'desc': [('equal', 'Write'), ('injected', ' a file')]}},
            'fields':   {'max_tokens': '8192'},
        },
        modifications=['replaced_system_prompt'],
        anthropic_beta=['computer-use-2024-10-22', 'max-tokens-3-5-sonnet-2024-07-15'],
        context_management={'edits': [{'type': 'truncate_messages'}, {'type': 'remove_tool_results'}]},
    )
    return {'name': 'expand_fixpoint', 'entries': [e0, e1]}


if __name__ == '__main__':
    main()
