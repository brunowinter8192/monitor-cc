# INFRASTRUCTURE
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = None
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
    global _ROOT
    _ROOT = root
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.update({'PROXY_LOG_ID': 'orch_diff', 'PROXY_PROJECT_PATH': '', 'MONITOR_CC_ROOT': tempfile.mkdtemp()})

def _run_all_cases() -> dict:
    results = {}
    for case in (_strip_cases, _bg_escape_cases, _tool_injection_cases, _discover_cases, _ghostty_cases,
                 _desktop_cases, _sweep_cases, _skill_cases, _hook_writer_cases, _hook_setup_cases):
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

def _discover_cases() -> dict:
    module = importlib.import_module('src.menubar.discover')
    calls = []
    for name in ('_refresh_cc_proc_cache', '_refresh_ghostty_tty_to_id', '_refresh_tmux_state', '_refresh_bg_task_cache',
                 '_read_hook_state', '_write_cwd_uuid_map'):
        setattr(module, name, lambda *a, _n=name: calls.append((_n, a)))
    module.log_menubar_change = lambda *a: calls.append(('log', a))
    session = module.SessionInfo
    infos = {
        'a': session('a', 'idle', False, 'ea', 'pa', False, '/cwd/a', 's1', ''),
        'b': session('b', 'working', True, 'eb', 'pb', True, '', 's2', 'tmux-b'),
        'c': session('c', 'idle', False, 'ec', 'pc', False, '/cwd/c', 's3', ''),
    }
    module.get_project_directories = lambda: [Path('/x/a'), Path('/x/boom'), Path('/x/none'), Path('/x/b'), Path('/x/c')]
    def process(project_dir, now):
        calls.append(('process', project_dir.name, now))
        if project_dir.name == 'boom':
            raise ValueError('boom')
        return infos.get(project_dir.name)
    module._process_project_dir = process
    module._cc_proc_cache.clear()
    module._cc_proc_cache.update({'1': ('ttys1', '/cwd/a'), '2': ('ttys2', '/cwd/c'), '3': ('', '/cwd/z')})
    module._ghostty_tty_to_id.clear()
    module._ghostty_tty_to_id.update({'ttys1': 'uuid1'})
    module.detect_main_desktop_numbers = lambda uuid_map, tty_map, now: calls.append(('detect', uuid_map, tty_map)) or {'/cwd/a': 4}
    module.time.time = lambda: 1000.0
    results = {}
    for with_mains in (True, False):
        calls.clear()
        if not with_mains:
            infos_only_workers = [infos['b']]
            module.get_project_directories = lambda: [Path('/x/b')]
        out = module.list_alive_sessions()
        results[f'discover:{with_mains}'] = {'out': [list(o) for o in out], 'calls': calls[:], 'timing_keys': sorted(module.get_last_session_timings())}
    return results

def _ghostty_cases() -> dict:
    module = importlib.import_module('src.menubar.ghostty')
    calls = []
    class R:
        def __init__(self, rc, out, err=''):
            self.returncode, self.stdout, self.stderr = rc, out, err
    state = {}
    module._ghostty_pid = lambda: state['pid']
    module._ghostty_child_ttys = lambda pid: state['ttys']
    module._write_markers = lambda ttys: [(t, 'M' + t) for t in ttys]
    module._query_terminal_names = lambda: state['reply']
    module._clear_markers = lambda tm: calls.append(('clear', tm))
    module.log_menubar_change = lambda *a: calls.append(('log', a))
    module.time.sleep = lambda secs: calls.append(('sleep', secs))
    scenarios = {
        'not_due': dict(pid=1, ttys=['a'], reply=None, last=95.0),
        'no_pid': dict(pid=0, ttys=['a'], reply=None, last=0.0),
        'no_new': dict(pid=1, ttys=['ttys1'], reply=None, last=0.0),
        'prune': dict(pid=1, ttys=[], reply=None, last=0.0),
        'query_none': dict(pid=1, ttys=['ttys1', 'ttys9'], reply=None, last=0.0),
        'query_rc': dict(pid=1, ttys=['ttys1', 'ttys9'], reply=R(1, '', ' boom '), last=0.0),
        'success': dict(pid=1, ttys=['ttys1', 'ttys9', 'ttys8'], reply=R(0, 'id1|||Mttys9\nid2|||other\nbad line\n'), last=0.0),
    }
    results = {}
    for name, sc in scenarios.items():
        state.update(sc)
        module._ghostty_tty_to_id.clear()
        module._ghostty_tty_to_id.update({'ttys1': 'u1', 'gone': 'u0'})
        module._ghostty_tty_last_refresh = sc['last']
        calls.clear()
        module._refresh_ghostty_tty_to_id(100.0)
        results[f'ghostty:{name}'] = {'map': dict(module._ghostty_tty_to_id), 'last': module._ghostty_tty_last_refresh, 'calls': calls[:]}
    return results

def _desktop_cases() -> dict:
    module = importlib.import_module('src.menubar.desktop_detection')
    calls = []
    module._resolve_cwds_to_desktops = lambda u, t: calls.append(('resolve', u, t)) or ({c: 3 for c in u}, {'ctx': 1})
    module._log_transitions = lambda r, c: calls.append(('log', r, c))
    results = {}
    module._det_cache, module._det_cache_ts, module._det_cache_cwds = {}, 0.0, frozenset()
    for label, uuid_map, now in (('first', {'/a': 'u'}, 10.0), ('cached', {'/a': 'u'}, 11.0), ('other', {'/b': 'u'}, 12.0),
                                 ('expired', {'/b': 'u'}, 12.0 + module._DET_CACHE_TTL + 1)):
        calls.clear()
        module._cgw_title_diag_logged = True
        out = module.detect_main_desktop_numbers(uuid_map, {}, now)
        results[f'desktop:{label}'] = {'out': out, 'calls': calls[:], 'diag': module._cgw_title_diag_logged, 'ts': module._det_cache_ts}
    return results

def _sweep_cases() -> dict:
    module = importlib.import_module('src.menubar.monitor_sweep_scheduler')
    calls = []
    class FakeThread:
        def __init__(self, target, name, daemon):
            calls.append(('thread', target.__name__, name, daemon))
        def start(self):
            calls.append(('start',))
    module.threading.Thread = FakeThread
    module._read_last_sweep_ts = lambda: calls.append(('read',)) or 100.0
    module._write_last_sweep_ts = lambda ts: calls.append(('write', ts))
    results = {}
    for label, in_progress, last, now in (('busy', True, None, 1e9), ('load_not_due', False, None, 200.0),
                                          ('due_loaded', False, 5.0, 5.0 + module.SWEEP_INTERVAL_SECS), ('not_due', False, 50.0, 60.0)):
        calls.clear()
        module._sweep_in_progress, module._last_sweep_ts = in_progress, last
        module.maybe_run_sweep_workflow(now)
        results[f'sweep:{label}'] = {'calls': calls[:], 'last': module._last_sweep_ts, 'busy': module._sweep_in_progress}
    return results

def _skill_cases() -> dict:
    module = importlib.import_module('src.menubar.skill_discovery')
    tmp = Path(tempfile.mkdtemp())
    (tmp / 'claude' / 'skills' / 'pers1').mkdir(parents=True)
    (tmp / 'claude' / 'skills' / 'pers1' / 'SKILL.md').write_text('x')
    (tmp / 'proj' / '.claude' / 'skills' / 'p1').mkdir(parents=True)
    (tmp / 'proj' / '.claude' / 'skills' / 'p1' / 'SKILL.md').write_text('x')
    plugin = tmp / 'plug'
    (plugin / '.claude-plugin').mkdir(parents=True)
    (plugin / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': 'pl', 'skills': ['sk/a', 'sk/missing']}))
    (plugin / 'sk' / 'a').mkdir(parents=True)
    (plugin / 'sk' / 'a' / 'SKILL.md').write_text('---\nname: alpha\n---\n')
    (tmp / 'claude' / 'settings.json').write_text(json.dumps({'enabledPlugins': {'pl@m': True, 'off@m': False}}))
    (tmp / 'claude' / 'plugins').mkdir()
    (tmp / 'claude' / 'plugins' / 'installed_plugins.json').write_text(json.dumps({'plugins': {'pl@m': [{'scope': 'user', 'installPath': str(plugin)}]}}))
    module.log_menubar = lambda *a: None
    results = {}
    for label, cwd in (('with_project', str(tmp / 'proj')), ('no_cwd', '')):
        out = module.discover_skills_workflow(cwd, tmp / 'claude')
        results[f'skills:{label}'] = json.loads(json.dumps([list(x) for x in out]).replace(str(tmp), '<TMP>'))
    return results

def _run_script(script: Path, home: Path, stdin: str = '') -> dict:
    proc = subprocess.run([sys.executable, str(script)], input=stdin, capture_output=True, text=True,
                          env={**os.environ, 'HOME': str(home)}, cwd=str(home), timeout=60)
    return {'rc': proc.returncode, 'out': proc.stdout.replace(str(home), '<HOME>'), 'err': proc.stderr.replace(str(home), '<HOME>')}

def _hook_writer_cases() -> dict:
    results = {}
    payloads = {'working': {'hook_event_name': 'UserPromptSubmit', 'session_id': 's1', 'cwd': '/c'},
                'idle': {'hook_event_name': 'Stop', 'session_id': 's2', 'cwd': '/c'},
                'other_event': {'hook_event_name': 'PreToolUse', 'session_id': 's3'},
                'no_session': {'hook_event_name': 'Stop'}}
    raw = dict(payloads, garbage=None)
    for label, payload in raw.items():
        with tempfile.TemporaryDirectory() as home_raw:
            home = Path(home_raw).resolve()
            stdin = 'not json{' if label == 'garbage' else json.dumps(payload)
            outcome = _run_script(_ROOT / 'src' / 'menubar' / 'hook_writer.py', home, stdin)
            state_file = home / 'Library' / 'Application Support' / 'com.brunowinter.monitor-cc-menubar' / 'hooks.json'
            state = json.loads(state_file.read_text()) if state_file.exists() else None
            if state:
                for entry in state.values():
                    entry['updated_ts'] = 'T'
            outcome['state'] = state
            results[f'hook_writer:{label}'] = outcome
    return results

def _hook_setup_cases() -> dict:
    results = {}
    settings_variants = {
        'absent': None,
        'empty': {},
        'malformed': 'MALFORMED',
        'stale': {'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [{'command': 'python3 /nonexistent/x.py'}, {'command': 'python3 /bin/sh'}]}], 'Stop': [{'hooks': [{'command': 'python3 /gone.py'}]}]}},
    }
    for script_rel in ('src/hooks/hook_setup.py', 'src/menubar/hook_setup.py'):
        for label, settings in settings_variants.items():
            for repeat in (1, 2):
                with tempfile.TemporaryDirectory() as raw:
                    base = Path(raw).resolve()
                    home = base / 'home'
                    (home / '.claude').mkdir(parents=True)
                    repo = base / 'repo'
                    shutil.copytree(_ROOT / 'src', repo / 'src', ignore=shutil.ignore_patterns('logs', '__pycache__'))
                    for cmd in (['git', 'init', '-q', '-b', 'main'], ['git', 'add', '-A'], ['git', '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-q', '-m', 'x']):
                        subprocess.run(cmd, cwd=repo, capture_output=True, check=True)
                    settings_file = home / '.claude' / 'settings.json'
                    if settings is not None:
                        settings_file.write_text(settings if isinstance(settings, str) else json.dumps(settings))
                    outcome = _run_script(repo / script_rel, home)
                    if repeat == 2:
                        outcome = _run_script(repo / script_rel, home)
                    outcome = {k: v.replace(str(repo), '<REPO>') if isinstance(v, str) else v for k, v in outcome.items()}
                    outcome['settings'] = settings_file.read_text().replace(str(repo), '<REPO>') if settings_file.exists() else None
                    results[f'hook_setup:{script_rel}:{label}:{repeat}'] = outcome
    return results

if __name__ == '__main__':
    orch_diff_workflow()
