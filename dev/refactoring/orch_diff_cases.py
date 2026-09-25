# INFRASTRUCTURE
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

_TRIGGERS = {
    'src.proxy.strip_bd_noise:_strip_bd_noise': 'pre\nauto-export: no changes since last export\npost',
    'src.proxy.strip_hook_prefix:_strip_hook_prefix': 'PreToolUse:Bash hook error: [python3 /x/y.py]: blocked\nrest',
    'src.proxy.strip_po:_strip_persisted_output_previews': '<persisted-output>\nOutput too large (1MB)\n\nPreview (first 2KB):\nbody\n</persisted-output>',
    'src.proxy.strip_git_lock:_strip_git_lock_advice': None,
    'src.proxy.strip_sn_notice:_strip_sn_notice': None,
    'src.proxy.strip_sr:_strip_system_reminders': "<system-reminder>\nThe task tools haven't been used recently\n</system-reminder>\ntail",
    'src.proxy.strip_sr:_strip_plan_mode_blocks': "<system-reminder>\nPlan mode is active\n</system-reminder>",
    'src.proxy.strip_bg_completed:_strip_bg_exit_notifications': 'Background command "x" completed (exit code 143)\nmore',
    'src.proxy.strip_interrupt_marker:_strip_interrupt_marker': '[Request interrupted by user]',
    'src.proxy.strip_bg_launch_ack:_strip_bg_launch_ack': 'Command running in background with ID: abc123. Output is being written to: /tmp/x.output',
    'src.proxy.strip_pasted_content:_strip_pasted_content_wrapper': '<pasted_content id="1">x</pasted_content id="1">',
}

# ORCHESTRATOR

def orch_diff_workflow() -> None:
    root, out_path = _parse_args()
    _prepare_environment(root)
    results = _run_all_cases()
    out_path.write_text(json.dumps(results, indent=1, sort_keys=True, default=repr))
    print(f'cases={len(results)}')

# FUNCTIONS

def _parse_args() -> tuple:
    return Path(sys.argv[1]).resolve(), Path(sys.argv[2])

def _prepare_environment(root: Path) -> None:
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.update({'PROXY_LOG_ID': 'orch_diff', 'PROXY_PROJECT_PATH': '', 'MONITOR_CC_ROOT': tempfile.mkdtemp()})

def _run_all_cases() -> dict:
    results = {}
    for case in (_strip_cases, _bg_escape_cases, _tool_injection_cases):
        results.update(_guard(case))
    return results

def _guard(case) -> dict:
    try:
        return case()
    except Exception as exc:
        return {case.__name__: f'CASE ERROR {exc!r}'}

def _shapes(trigger: str) -> list:
    text_block = {'type': 'text', 'text': trigger}
    return [
        trigger, 'no trigger here', '', 7, None,
        [text_block], [{'type': 'text', 'text': 'plain'}], [], ['bare string', 3],
        [text_block, {'type': 'image', 'source': {}}, 'x', {'type': 'other'}],
        [{'type': 'tool_result', 'content': trigger}],
        [{'type': 'tool_result', 'content': 'plain'}],
        [{'type': 'tool_result', 'content': [text_block, {'type': 'image'}, 'y', {'type': 'text', 'text': 'plain'}]}],
        [{'type': 'tool_result', 'content': None}],
        [{'type': 'tool_result'}],
        [{'type': 'text'}],
        [{'type': 'text', 'text': trigger + '\n' + trigger}],
    ]

def _identity_flags(inp, out) -> list:
    if isinstance(inp, list) and isinstance(out, list) and len(inp) == len(out):
        return [a is b for a, b in zip(inp, out)]
    return []

def _snapshot(value, inp) -> dict:
    return {'value': value, 'same_top': value is inp, 'same_items': _identity_flags(inp, value)}

def _strip_cases() -> dict:
    results = {}
    for key, trigger in _TRIGGERS.items():
        module_name, fn_name = key.split(':')
        module = importlib.import_module(module_name)
        fn = getattr(module, fn_name)
        text = trigger if trigger is not None else _module_trigger(module_name, module)
        for index, shape in enumerate(_shapes(text)):
            results[f'{key}#{index}'] = _apply(fn, shape)
    return results

def _module_trigger(module_name: str, module) -> str:
    if module_name.endswith('strip_git_lock'):
        return 'x ' + module._GIT_LOCK_ADVICE + '\ny'
    return 'a\n' + module._SN_NOTICE_PARAGRAPH + '\nb'

def _apply(fn, shape):
    inp = json.loads(json.dumps(shape))
    out = fn(inp)
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[1], list):
        return {'main': _snapshot(out[0], inp), 'removed': out[1], 'input_after': inp}
    return {'main': _snapshot(out, inp), 'input_after': inp}

def _bg_escape_cases() -> dict:
    module = importlib.import_module('src.proxy.bg_escape')
    events = []
    module._send_escape_key = lambda session: events.append(('send', session)) or True
    module._log_bg_escape_event = lambda *a, **k: events.append(('log', a, k))
    ack = 'Command running in background with ID: %s. Output is being written to: /tmp/x'
    scenarios = {
        'main_ctx': ({'a': [ack % 't1', 'other', 5]}, 'main', '/p/proj'),
        'worker_ok': ({'a': [ack % 't2'], 'b': [ack % 't3', ack % 't2']}, 'worker:w1', '/p/proj'),
        'worker_no_project': ({'a': [ack % 't4']}, 'worker:w1', ''),
        'no_id': ({'a': ['Command running in background with ID: ']}, 'worker:w1', '/p/proj'),
        'empty': ({}, 'main', ''),
    }
    results = {}
    for name, (removed, ctx, project) in scenarios.items():
        module._escaped_task_ids.clear()
        events.clear()
        module._trigger_bg_escape(removed, ctx, project)
        results[f'bg_escape:{name}'] = {'events': list(events), 'escaped': sorted(module._escaped_task_ids)}
    return results

def _tool_injection_cases() -> dict:
    module = importlib.import_module('src.proxy.tool_injection')
    store = {
        'iterative-dev': [{'name': 'z_tool'}, {'name': 'a_tool'}, {'name': 'shared'}],
        'other': [{'name': 'o2'}, {'name': 'o1'}, {'name': 'shared'}],
    }
    payloads = {
        'no_tools': {'model': 'm'},
        'empty_tools': {'tools': []},
        'with_tools': {'tools': [{'name': 'shared'}, {'name': 'keep'}]},
    }
    results = {}
    for excluded in (False, True):
        for plugins in ([], ['other'], ['iterative-dev', 'other', 'other', 'missing']):
            for store_state in (store, {}):
                module._is_project_excluded = lambda project, e=excluded: e
                module._load_schema_store = lambda s=store_state: s
                module._load_active_plugins = lambda project, p=plugins: p
                for pname, payload in payloads.items():
                    inp = json.loads(json.dumps(payload))
                    out = module.inject_mcp_tools(inp, '/p')
                    results[f'inject:{excluded}:{plugins}:{bool(store_state)}:{pname}'] = {'out': out, 'same': out is inp, 'input_after': inp}
    return results

if __name__ == '__main__':
    orch_diff_workflow()
