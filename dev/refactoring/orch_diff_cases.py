# INFRASTRUCTURE
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = None
_REAL_RUN = subprocess.run
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
                 _desktop_cases, _sweep_cases, _skill_cases, _hook_writer_cases, _hook_setup_cases,
                 _pane_loop_cases, _gpu_status_cases, _misc_flow_cases):
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

class _Stop(BaseException):
    pass

def _recorder(calls: list, name: str, script=None, default=None):
    queue = list(script) if script is not None else None
    def fn(*args, **kwargs):
        calls.append((name, _clean(repr(args)), _clean(repr(sorted(kwargs.items())))))
        if queue is None:
            return default
        value = queue.pop(0) if queue else default
        if isinstance(value, Exception):
            raise value
        return value
    return fn

def _clean(text: str) -> str:
    text = re.sub(r' at 0x[0-9a-f]+', '', text)
    return re.sub(r"from '[^']*'", "from '<M>'", text)

def _install_common(module, calls: list, stop_after: int, wait_name: str = 'wait_for_input') -> None:
    waits = {'n': 0}
    def wait(*args, **kwargs):
        calls.append((wait_name, repr(args), repr(kwargs)))
        waits['n'] += 1
        if waits['n'] >= stop_after:
            raise _Stop()
    setattr(module, wait_name, wait)
    for name in ('setup_keyboard_input', 'enable_mouse', 'disable_mouse', 'restore_terminal', 'hide_cursor', 'show_cursor', 'register_ram_dump', 'log_pane_error', 'write_frame'):
        if hasattr(module, name):
            setattr(module, name, _recorder(calls, name))
    clock = {'t': 1000.0}
    def fake_time():
        clock['t'] += 1.7
        return clock['t']
    import time as time_module
    time_module.time = fake_time

def _run_loop(loop_fn, calls: list) -> None:
    import contextlib, io
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            loop_fn()
    except _Stop:
        calls.append(('STOP',))
    calls.append(('stdout', buffer.getvalue()))

def _pane_loop_cases() -> dict:
    results = {}
    results.update(_gpu_loop_case())
    results.update(_news_loop_cases())
    for label, module_name, fn_name, prefix, feedback in (
            ('tokens', 'src.panes.token_pane', 'run_tokens_loop', 'tokens', '_cache_copy_feedback_until'),
            ('warnings', 'src.panes.warnings_pane', 'run_warnings_loop', 'warnings', '_error_copy_feedback_until'),
            ('proxy', 'src.proxy_display.pane', 'run_proxy_loop', 'proxy', '_copy_feedback_until'),
            ('worker_proxy', 'src.proxy_display.worker_proxy_pane', 'run_worker_proxy_loop', 'worker_proxy', '_worker_copy_feedback_until'),
            ('worker_tokens', 'src.workers.worker_tokens_pane', 'run_worker_tokens_loop', 'worker_tokens', '_worker_tokens_copy_feedback_until')):
        results.update(_data_pane_case(label, module_name, fn_name, prefix, feedback))
    return results

def _gpu_loop_case() -> dict:
    module = importlib.import_module('src.gpu_pane.pane')
    calls = []
    _install_common(module, calls, 6)
    module._poll_gpu_input = _recorder(calls, 'poll', [(False, True), RuntimeError('x'), (False, False), (True, False), (False, False)])
    tuples = [
        (['p1'], ['a1'], ['n1'], ['t1'], {'e': 1}, ['c1'], 5.0, 6.0, True),
        (['p2'], ['a2'], ['n2'], ['t2'], {'e': 2}, ['c2'], 7.0, 8.0, False),
        (['p3'], ['a3'], ['n3'], ['t3'], {'e': 3}, None, 9.0, 10.0, False),
        (['p4'], ['a4'], ['n4'], ['t4'], {'e': 4}, ['c4'], 11.0, 12.0, True),
    ]
    module._refresh_gpu_data = _recorder(calls, 'refresh', tuples)
    module._build_gpu_output = _recorder(calls, 'build', ['out1', 'out2', 'out3'])
    _run_loop(module.run_gpu_loop, calls)
    return {'loop:gpu': calls}

def _news_loop_cases() -> dict:
    results = {}
    module = importlib.import_module('src.news_pane.pane')
    calls = []
    _install_common(module, calls, 7)
    module._poll_news_input = _recorder(calls, 'poll', [(False, False), (False, True), RuntimeError('y'), (True, False), (False, False), (False, False)])
    module._fetch_news_status = _recorder(calls, 'fetch', [{'s': 1}, {'s': 2}, {'s': 3}, {'s': 4}])
    module._build_news_output = _recorder(calls, 'build', ['n1', 'n2', 'n3'])
    _run_loop(module.run_news_loop, calls)
    results['loop:news'] = calls
    module = importlib.import_module('src.news_pane.log_pane')
    calls = []
    class Term:
        columns, lines = 100, 40
    module.os.get_terminal_size = lambda: Term()
    module.find_log_file = _recorder(calls, 'find_log', ['/log/a', None, RuntimeError('z'), '/log/a', '/log/a'])
    module.find_current_run_lines = _recorder(calls, 'run_lines', [['l1'], ['l2'], ['l3']])
    module.filter_events = _recorder(calls, 'filter', [['e1'], ['e2']])
    module._render_log_pane = _recorder(calls, 'render', ['A', 'A', 'B', 'B'])
    module.log_pane_error = _recorder(calls, 'log_err')
    sleeps = {'n': 0}
    def sleep(secs):
        calls.append(('sleep', secs))
        sleeps['n'] += 1
        if sleeps['n'] >= 6:
            raise _Stop()
    module.time.sleep = sleep
    _run_loop(module.run_news_log_loop, calls)
    results['loop:news_log'] = calls
    return results

def _data_pane_case(label: str, module_name: str, fn_name: str, prefix: str, feedback: str) -> dict:
    module = importlib.import_module(module_name)
    calls = []
    _install_common(module, calls, 8)
    monitor = importlib.import_module('src.core.monitor')
    monitor._get_newest_main_session = _recorder(calls, 'newest_session', default='sess-1')
    monitor._get_session_start_ts = _recorder(calls, 'session_start', default=42.0)
    poll_name = {'tokens': '_poll_tokens_input', 'warnings': '_poll_warnings_input', 'proxy': '_poll_proxy_input',
                 'worker_proxy': '_poll_worker_proxy_input', 'worker_tokens': '_poll_worker_tokens_input'}[label]
    refresh_name = poll_name.replace('_poll_', '_refresh_').replace('_input', '_data')
    build_name = poll_name.replace('_poll_', '_build_').replace('_input', '_output')
    setattr(module, poll_name, _recorder(calls, 'poll', [False, False, RuntimeError('q'), True, False, False, False]))
    if label == 'tokens':
        refreshes = [(False, 1.0, 2.0), (True, 3.0, 4.0), (False, 5.0, 6.0), (False, 7.0, 8.0), (False, 9.0, 10.0), (False, 11.0, 12.0), (False, 13.0, 14.0)]
    else:
        refreshes = [(False, 1.0), (True, 3.0), (False, 5.0), (False, 7.0), (False, 9.0), (False, 11.0), (False, 13.0)]
    setattr(module, refresh_name, _recorder(calls, 'refresh', refreshes))
    if label == 'warnings':
        builds = [('out1', 'h1'), ('out1', 'h1'), ('', 'h3'), ('out4', 'h4'), ('out5', 'h5')]
    else:
        builds = ['o1', 'o1', 'o3', 'o4', 'o5']
    setattr(module, build_name, _recorder(calls, 'build', builds))
    setattr(module, feedback, {'a': 1e9, 'b': 0.0})
    _run_loop(getattr(module, fn_name), calls)
    state = {'feedback': dict(getattr(module, feedback))}
    for name in ('_proxy_current_main_session', '_proxy_session_start_ts'):
        if hasattr(module, name):
            state[name] = getattr(module, name)
    return {f'loop:{label}': {'calls': calls, 'state': state}}

def _gpu_status_cases() -> dict:
    module = importlib.import_module('src.gpu_pane.status')
    tmp = Path(tempfile.mkdtemp())
    module.RAG_LOCKS_DIR = tmp
    files = {
        'server-port-1.json': {'port': 1, 'pid': 100, 'name': 'presetA'},
        'server-port-2.json': {'port': 2, 'pid': 200, 'name': 'presetA'},
        'server-port-3.json': {'port': 3, 'pid': 300, 'name': 'other'},
        'server-port-4.json': {'pid': 400, 'name': 'noport'},
        'server-port-5.json': {'port': 5, 'pid': 500, 'name': 'dead'},
        'server-port-6.json': {'port': 6, 'pid': 600, 'name': 'perm'},
        'server-port-7.json': {'port': 7, 'name': 'nopid'},
    }
    for name, state in files.items():
        (tmp / name).write_text(json.dumps(state))
    (tmp / 'server-port-8.json').write_text('{not json')
    warns = []
    module._warn = lambda *a: warns.append(a)
    module._check_legacy_files = lambda: warns.append(('legacy',))
    module._ensure_preset_names = lambda: warns.append(('ensure',))
    module.PRESET_NAMES[:] = ['presetA', 'presetB']
    module._status_for_preset = lambda n, st: {'preset': n, 'state': st}
    module._status_for_state = lambda st: {'arb': st}
    def kill(pid, sig):
        if pid == 500:
            raise ProcessLookupError()
        if pid == 600:
            raise PermissionError()
    module.os.kill = kill
    module._last_anomalies = ['old']
    out = module.all_statuses()
    return {'gpu_status': {'out': out, 'warns': [[str(x).replace(str(tmp), '<TMP>') for x in w] for w in sorted(warns, key=repr)], 'anomalies': list(module._last_anomalies)}}

def _misc_flow_cases() -> dict:
    results = {}
    monitor = importlib.import_module('src.core.monitor')
    calls = []
    for mode_name in ('MODE_WORKER_TOKENS', 'MODE_TOKENS', 'MODE_WARNINGS', 'MODE_PROXY', 'MODE_WORKER_PROXY', 'bogus'):
        mode = getattr(monitor, mode_name, mode_name)
        pkg = {'MODE_WORKER_TOKENS': ('src.workers', 'run_worker_tokens_loop'), 'MODE_TOKENS': ('src.panes', 'run_tokens_loop'),
               'MODE_WARNINGS': ('src.panes', 'run_warnings_loop'), 'MODE_PROXY': ('src.proxy_display', 'run_proxy_loop'),
               'MODE_WORKER_PROXY': ('src.proxy_display', 'run_worker_proxy_loop')}.get(mode_name)
        if pkg:
            setattr(importlib.import_module(pkg[0]), pkg[1], lambda n=mode_name: calls.append(n))
        try:
            monitor.run_monitor('projX', mode)
            outcome = 'ok'
        except ValueError as exc:
            outcome = repr(exc)
        results[f'monitor:{mode_name}'] = {'outcome': outcome, 'calls': calls[:], 'filter': monitor.active_project_filter, 'mode': monitor.active_mode}
        calls.clear()
    launcher = importlib.import_module('src.tmux_launcher')
    launch_scenarios = {'no_tmux': (False, False, True, None), 'inside': (True, True, True, None), 'stale': (True, False, True, 'proj'), 'fresh': (True, False, False, None), 'no_limit': (True, False, False, 'p2')}
    for label, (installed, inside, exists, project) in launch_scenarios.items():
        calls = []
        launcher.is_tmux_installed = lambda v=installed: v
        launcher.is_inside_tmux = lambda v=inside: v
        launcher.generate_session_name = lambda p: 'sess-' + str(p)
        launcher.check_session_exists = lambda n, v=exists: v
        launcher.kill_session = lambda n: calls.append(('kill', n))
        launcher._build_mode_commands = lambda sp, pf: {'cmds': (sp, pf)}
        launcher.get_global_history_limit = lambda l=label: None if l == 'no_limit' else '2000'
        launcher.restore_global_history_limit = lambda v: calls.append(('restore', v))
        launcher._create_windows = lambda n, c: calls.append(('windows', n, c))
        launcher.configure_tmux_session = lambda n, sp, pa: calls.append(('configure', n, sp, pa))
        launcher.subprocess.run = lambda cmd, **kw: calls.append(('run', cmd))
        import contextlib, io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                launcher.launch_split_screen(project, '/s.py')
            outcome = 'ok'
        except SystemExit as exc:
            outcome = f'exit {exc.code}'
        results[f'launch:{label}'] = {'outcome': outcome, 'calls': calls, 'stdout': buf.getvalue()}
    cli = importlib.import_module('src.dual_log_cli.__main__')
    tmp = Path(tempfile.mkdtemp())
    for label, exists in (('missing', False), ('present', True)):
        cli.resolve_dual_log_dir = lambda e=exists: (tmp if e else tmp / 'absent')
        for name in ('_run_sessions', '_run_search', '_run_reqs', '_run_msgs', '_run_expand'):
            setattr(cli, name, lambda d, a, n=name: n)
        outs = {}
        for command in ('sessions', 'search', 'reqs', 'msgs', 'expand'):
            cli._parse_args = lambda argv, c=command: type('A', (), {'command': c})()
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                outs[command] = [cli.main([]), buf.getvalue().replace(str(tmp), '<TMP>')]
        results[f'dual_main:{label}'] = outs
    wf = importlib.import_module('src.ccwrap.wrapper')
    results['ccwrap_run'] = _ccwrap_cases()
    return results

def _ccwrap_cases() -> dict:
    subprocess.run = _REAL_RUN
    out = {}
    argv_cases = {'default': [], 'project': ['--project', '/p', 'x', 'y'], 'missing': ['--project'], 'pass_only': ['a', '--project', '/q']}
    for label, argv in argv_cases.items():
        code = ('import sys\nsys.argv = ["m"] + %r\nimport src.ccwrap.wrapper as w\ncaptured = {}\n'
                'w.run = lambda cmd, log_dir: captured.update(cmd=cmd) or 7\nimport runpy\n'
                'try:\n    runpy.run_module("src.ccwrap", run_name="__main__")\nexcept SystemExit as e:\n    print("EXIT", e.code)\nprint(captured)\n') % (argv,)
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(_ROOT))
        out[f'main:{label}'] = [proc.returncode, proc.stdout, proc.stderr[-200:]]
    for label, cmd in (('echo', ['/bin/sh', '-c', 'printf abc; exit 0']), ('exit3', ['/bin/sh', '-c', 'exit 3'])):
        tmp = Path(tempfile.mkdtemp())
        code = ('import sys\nfrom pathlib import Path\nfrom src.ccwrap.wrapper import run\n'
                'w = __import__("src.ccwrap.wrapper", fromlist=["x"])\nw._get_winsize = lambda: (24, 80)\n'
                'print("RC", run(%r, Path(%r)))\n') % (cmd, str(tmp))
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(_ROOT), stdin=subprocess.DEVNULL)
        out[f'run:{label}'] = [proc.returncode, proc.stdout, proc.stderr[-300:], sorted(p.suffix for p in tmp.iterdir())]
    return out

if __name__ == '__main__':
    orch_diff_workflow()
