#!/usr/bin/env python3
"""Unit tests for the whole-stripped tool row expand feature (Milestone 2, 2026-09).

Coverage:
  - render_sections._render_whole_stripped_tool: collapsed-row bytes/key shape, expanded body with
    a resolved tool_def (description + params), expanded fallback when tool_def is None.
  - render_sections.render_tools: use_dual whole-stripped loop wires _original_tools_by_name
    through to the new function; forwarded-tool rows and every other section are untouched.
  - parser._find_original_log_path / accumulate_original_tools: path derivation, per-family latest-
    snapshot overwrite behavior, missing-file no-op.

Run: python3 dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.proxy_display.render_sections import _render_whole_stripped_tool, render_tools
from src.proxy_display.parser import _find_original_log_path
from src.proxy_display.dual_log_accumulator import accumulate_original_tools

PASS = []
FAIL = []


def check(name, condition, msg=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {msg}' if msg else ''))


# ── _render_whole_stripped_tool ────────────────────────────────────────────────

def t01_collapsed_row_key_and_symbol():
    lines, keys = _render_whole_stripped_tool(3, 'Agent', {'description': 'x'}, {})
    check('T01_one_line_collapsed', len(lines) == 1, f'lines={lines}')
    check('T01_key_shape', keys == [('stripped_tool', 3, 'Agent')], f'keys={keys}')
    check('T01_symbol_collapsed', '▶ Agent' in lines[0], repr(lines[0]))
    check('T01_yellow_bg', '\033[48;2;94;81;47m' in lines[0], repr(lines[0]))


def t02_expanded_symbol_flips():
    key = ('stripped_tool', 0, 'ListAgents')
    lines, keys = _render_whole_stripped_tool(0, 'ListAgents', {'description': 'd'}, {key: True})
    check('T02_symbol_expanded', '▼ ListAgents' in lines[0], repr(lines[0]))
    check('T02_key_still_first', keys[0] == key)


def t03_expanded_shows_description_and_params():
    key = ('stripped_tool', 2, 'SendFeedback')
    tool_def = {
        'description': 'Send feedback\nto the team',
        'input_schema': {
            'type': 'object',
            'properties': {
                'message': {'type': 'string', 'description': 'The feedback text'},
                'urgent': {'type': 'boolean'},
            },
            'required': ['message'],
        },
    }
    lines, keys = _render_whole_stripped_tool(2, 'SendFeedback', tool_def, {key: True})
    body = '\n'.join(lines)
    check('T03_desc_line1', 'Send feedback' in body, body)
    check('T03_desc_line2', 'to the team' in body, body)
    check('T03_required_param_marked', 'message*: string — The feedback text' in body, body)
    check('T03_optional_param_no_marker', 'urgent: boolean' in body, body)
    check('T03_all_lines_yellow_bg', all('\033[48;2;94;81;47m' in l for l in lines), lines)
    check('T03_expanded_key_count', keys.count(None) == len(lines) - 1, f'keys={keys}')


def t04_expanded_no_tool_def_shows_fallback():
    key = ('stripped_tool', 5, 'Workflow')
    lines, keys = _render_whole_stripped_tool(5, 'Workflow', None, {key: True})
    check('T04_two_lines', len(lines) == 2, f'lines={lines}')
    check('T04_fallback_text', '(original definition unavailable)' in lines[1], repr(lines[1]))
    check('T04_fallback_yellow', '\033[48;2;94;81;47m' in lines[1], repr(lines[1]))
    check('T04_fallback_key_is_none', keys == [key, None], f'keys={keys}')


# ── render_tools integration ────────────────────────────────────────────────────

def _mk_dual_entry(tools_names, tools_defs, stripped_tools, original_tools_by_name=None):
    return {
        'tools_count': len(tools_defs),
        'tools_total_chars': sum(len(json.dumps(t)) for t in tools_defs),
        'tools_hash': 'h1',
        'tools_names': tools_names,
        'tools_defs': tools_defs,
        '_stripped_spans': {'tools': stripped_tools},
        '_injected_spans': {'tools': {}},
        '_original_tools_by_name': original_tools_by_name or {},
        'deferred_tools_names': [],
    }


def t05_whole_stripped_row_uses_original_def_when_available():
    entry = _mk_dual_entry(
        tools_names=['Bash'],
        tools_defs=[{'name': 'Bash', 'description': 'Run bash', 'input_schema': {}}],
        stripped_tools={'Agent': {'whole': True}},
        original_tools_by_name={'Agent': {'description': 'Delegate to a sub-agent', 'input_schema': {}}},
    )
    expand_states = {('tools', 0): True, ('stripped_tool', 0, 'Agent'): True}
    lines, keys = render_tools(0, entry, None, expand_states, 120)
    body = '\n'.join(lines)
    check('T05_agent_row_present', '▼ Agent' in body, body)
    check('T05_agent_original_desc_shown', 'Delegate to a sub-agent' in body, body)
    check('T05_agent_key_present', ('stripped_tool', 0, 'Agent') in keys, f'keys={keys}')


def t06_whole_stripped_row_collapsed_falls_back_when_no_original_available():
    entry = _mk_dual_entry(
        tools_names=['Bash'],
        tools_defs=[{'name': 'Bash', 'description': 'Run bash', 'input_schema': {}}],
        stripped_tools={'ListAgents': {'whole': True}},
        original_tools_by_name={},  # simulates worker-pane path: never attached / not yet resolved
    )
    expand_states = {('tools', 0): True}
    lines, keys = render_tools(0, entry, None, expand_states, 120)
    body = '\n'.join(lines)
    check('T06_row_present_collapsed', '▶ ListAgents' in body, body)
    check('T06_row_clickable', ('stripped_tool', 0, 'ListAgents') in keys, f'keys={keys}')
    check('T06_no_content_shown_collapsed', 'unavailable' not in body, body)


def t07_forwarded_tool_row_unaffected():
    # Same forwarded-tool rendering path as before this milestone — no whole-stripped tools at all.
    tool_def = {'name': 'Bash', 'description': 'Run bash commands', 'input_schema': {
        'properties': {'command': {'type': 'string', 'description': 'the command'}}, 'required': ['command'],
    }}
    entry = _mk_dual_entry(tools_names=['Bash'], tools_defs=[tool_def], stripped_tools={})
    expand_states = {('tools', 0): True, ('tool', 0, 0): True}
    lines, keys = render_tools(0, entry, None, expand_states, 120)
    body = '\n'.join(lines)
    check('T07_bash_header_present', '▼ Bash' in body, body)
    check('T07_bash_desc_shown', 'Run bash commands' in body, body)
    check('T07_bash_param_shown', 'command*: string — the command' in body, body)
    check('T07_no_stripped_tool_keys', not any(isinstance(k, tuple) and k[0] == 'stripped_tool' for k in keys), keys)


# ── parser: _find_original_log_path / accumulate_original_tools ────────────────

def t08_find_original_log_path():
    p = _find_original_log_path(Path('/x/y/src/logs/api_requests_abc123.jsonl'))
    check('T08_path_shape', str(p) == '/x/y/src/logs/dual_log/api_requests_abc123_original.jsonl', str(p))
    check('T08_none_input', _find_original_log_path(None) is None)


def t09_accumulate_original_tools_missing_file_is_noop():
    acc = {}
    new_pos = accumulate_original_tools(Path('/no/such/file_original.jsonl'), 0, acc)
    check('T09_pos_unchanged', new_pos == 0, new_pos)
    check('T09_acc_empty', acc == {}, acc)


def t10_accumulate_original_tools_latest_snapshot_per_family():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'x_original.jsonl'
        lines = [
            {'model': 'claude-haiku-4-5', 'payload': {'messages': []}},  # no tools key at all
            {'model': 'claude-fable-5-1', 'payload': {'tools': [
                {'name': 'Bash', 'description': 'run bash v1'},
                {'name': 'Agent', 'description': 'agent v1'},
            ]}},
            {'model': 'claude-fable-5-1', 'payload': {'tools': [
                {'name': 'Bash', 'description': 'run bash v2'},
            ]}},
        ]
        path.write_text('\n'.join(json.dumps(l) for l in lines) + '\n')
        acc = {}
        pos = accumulate_original_tools(path, 0, acc)
        check('T10_haiku_family_absent', 'haiku' not in acc, acc)
        check('T10_opus_family_present', 'opus' in acc, acc)
        check('T10_latest_snapshot_only', acc['opus'] == {'Bash': {'name': 'Bash', 'description': 'run bash v2'}}, acc.get('opus'))
        check('T10_position_advanced', pos == len(path.read_text().encode('utf-8')), pos)

        # Incremental: a new line appended, read from pos, should merge onto the SAME dict object
        opus_dict_ref = acc['opus']
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'model': 'claude-fable-5-1', 'payload': {'tools': [
                {'name': 'Write', 'description': 'write v1'},
            ]}}) + '\n')
        pos2 = accumulate_original_tools(path, pos, acc)
        check('T10_incremental_overwrite', acc['opus'] == {'Write': {'name': 'Write', 'description': 'write v1'}}, acc['opus'])
        check('T10_same_dict_reference_preserved', acc['opus'] is opus_dict_ref)
        check('T10_position_advanced_again', pos2 > pos)


if __name__ == '__main__':
    tests = [
        t01_collapsed_row_key_and_symbol, t02_expanded_symbol_flips,
        t03_expanded_shows_description_and_params, t04_expanded_no_tool_def_shows_fallback,
        t05_whole_stripped_row_uses_original_def_when_available,
        t06_whole_stripped_row_collapsed_falls_back_when_no_original_available,
        t07_forwarded_tool_row_unaffected,
        t08_find_original_log_path, t09_accumulate_original_tools_missing_file_is_noop,
        t10_accumulate_original_tools_latest_snapshot_per_family,
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
