# INFRASTRUCTURE
import argparse
import importlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report

_EXPECTED_HEADERS = {
    'sessions': '[Sessions] · RAG · Models · Launch',
    'rag': 'Sessions · [RAG] · Models · Launch',
    'models': 'Sessions · RAG · [Models] · Launch',
    'launch': 'Sessions · RAG · Models · [Launch]',
}
_EXPECTED_PROJECTS = [
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/reddit-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/iterative-dev',
    '/Users/brunowinter2000/Documents/ai/trading',
    '/Users/brunowinter2000/Documents/ai/trading_ai',
    '/Users/brunowinter2000/Documents/ai/monitor-cc',
    '/Users/brunowinter2000/Documents/general',
    '/Users/brunowinter2000/Documents/wise2627',
]
_ROOT_DIR = '/Users/brunowinter2000/Documents/ai/monitor-cc'

# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    if args.case:
        _run_case_in_child(args.case)
        return
    names = sorted(_CASES)
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(_spawn_case, names))
    text = _build_report(results)
    path = write_report(__file__, text)
    print(text)
    print(f'report: {path}')
    if any(not r['ok'] for r in results):
        sys.exit(1)

# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--case')
    return p.parse_args()

def _spawn_case(name: str) -> dict:
    r = subprocess.run([sys.executable, '-m', 'dev.session_launcher.t2_launch_tab', '--case', name],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=120)
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines:
        return {'name': name, 'ok': False, 'detail': f'rc={r.returncode} stderr={r.stderr.strip()[-400:]}'}
    out = json.loads(lines[-1])
    out['name'] = name
    return out

def _run_case_in_child(name: str) -> None:
    try:
        detail = _CASES[name]()
        print(json.dumps({'ok': True, 'detail': detail}))
    except AssertionError as exc:
        print(json.dumps({'ok': False, 'detail': f'ASSERT {exc}'}))
    except Exception as exc:
        print(json.dumps({'ok': False, 'detail': f'ERROR {exc!r}'}))

def _imp(name: str):
    return importlib.import_module(f'src.menubar.{name}')

def _session(name: str, desktop, worker: bool = False):
    S = _imp('discover').SessionInfo
    return S(name=name, status='idle', has_bg=False, encoded_dir=f'-{name}', project_name=name,
             is_worker=worker, cwd='' if worker else f'/tmp/{name}', session_id=f'sid-{name}',
             tmux_session_name='', desktop_no=desktop)

class _FakeSessions:
    def __init__(self, items):
        self.items = items

    def refresh(self):
        return self.items

    @property
    def bg_by_project(self):
        return {}

class _FakeApp:
    def __init__(self, sessions):
        self.settings = SimpleNamespace(panel_width=380, panel_min_height=460)
        self._panel_controller = None
        self.sessions = _FakeSessions(sessions)

def _title(btn) -> str:
    return str(btn.attributedTitle().string())

def _case_headers() -> str:
    app = _FakeApp([])
    got = {}
    pm = _imp('panel_manager').PanelManager(app)
    pm.rebuild([])
    got['sessions'] = _title(pm._widgets.header_btn)
    rag = _imp('rag_controller').RagController(app)
    rag.rebuild()
    got['rag'] = _title(rag._rag_header_btn)
    models = _imp('model_controller').ModelController(app)
    models.rebuild()
    got['models'] = _title(models._models_header_btn)
    launch = _imp('launch_controller').LaunchController(app)
    launch.open()
    got['launch'] = _title(launch._launch_header_btn)
    assert got == _EXPECTED_HEADERS, f'got {got}'
    assert all(('Auto' + '-Jump') not in v for v in got.values())
    return json.dumps(got, ensure_ascii=False)

def _case_occupied_marking() -> str:
    lc = _imp('launch_controller')
    sessions = [_session('a', 1), _session('b', 3), _session('w', None, worker=True), _session('c', None)]
    ctl = lc.LaunchController(_FakeApp(sessions))
    ctl.open()
    enabled = {d: bool(b.isEnabled()) for d, b in ctl._desktop_btns.items()}
    titles = {d: _title(b) for d, b in ctl._desktop_btns.items()}
    assert enabled == {1: True, 2: True, 3: True, 4: True, 5: True}, f'enabled {enabled}'
    assert titles == {1: ' 1* ', 2: ' 2 ', 3: ' 3* ', 4: ' 4 ', 5: ' 5 '}, f'titles {titles}'
    row = ctl._desktop_btns[1].superview()
    assert len(row.subviews()) == 5, f'desktop row has {len(row.subviews())} subviews, want only the 5 buttons'
    assert sorted(round(v.frame().origin.x) for v in row.subviews()) == [0, 40, 80, 120, 160], 'buttons not starting at x=0'
    ctl.handle_select_desktop(1)
    assert ctl._selected_desktop == 1, 'occupied desktop was refused'
    assert _title(ctl._desktop_btns[1]) == '[1*]', _title(ctl._desktop_btns[1])
    ctl.handle_select_desktop(2)
    assert ctl._selected_desktop == 2
    assert _title(ctl._desktop_btns[2]) == '[2]', _title(ctl._desktop_btns[2])
    assert _title(ctl._desktop_btns[1]) == ' 1* ', 'star lost after deselect'
    ctl.handle_select_desktop(7)
    assert ctl._selected_desktop == 2, 'desktop outside 1-5 changed the selection'
    return f'enabled {enabled}, titles {titles}, row = 5 buttons only at x=0..160, select occupied 1 -> [1*], select 2 -> [2], select 7 ignored'

def _case_tick_and_selection() -> str:
    lc = _imp('launch_controller')
    app = _FakeApp([_session('a', 1)])
    ctl = lc.LaunchController(app)
    ctl.open()
    ctl._launch_open = True
    ctl.handle_select_desktop(2)
    with patch.object(ctl, 'rebuild', wraps=ctl.rebuild) as rb:
        ctl.tick(app.sessions.items)
        assert rb.call_count == 0, 'rebuilt without change'
        app.sessions.items = [_session('a', 1), _session('b', 2)]
        ctl.tick(app.sessions.items)
        assert rb.call_count == 1, f'rebuild calls {rb.call_count}'
    assert ctl._selected_desktop == 2, 'selection cleared when its desktop became occupied'
    assert _title(ctl._desktop_btns[2]) == '[2*]', _title(ctl._desktop_btns[2])
    ctl._selected_desktop = 3
    ctl.open()
    assert ctl._selected_desktop is None, 'open() did not reset selection'
    ctl._launch_open = False
    with patch.object(ctl, 'rebuild') as rb:
        app.sessions.items = []
        ctl.tick(app.sessions.items)
        assert rb.call_count == 0, 'closed panel rebuilt'
    return 'tick: no change -> 0 rebuilds, change -> 1 rebuild, selection kept and shows [2*], open() resets, closed panel idle'

def _case_project_rows() -> str:
    lc = _imp('launch_controller')
    ctl = lc.LaunchController(_FakeApp([]))
    ctl.open()
    views = list(ctl._launch_sv.arrangedSubviews())
    buttons = [v for v in views if hasattr(v, 'tag') and hasattr(v, 'attributedTitle')]
    assert len(buttons) == 10, f'project buttons {len(buttons)}'
    assert [b.tag() for b in buttons] == list(range(10))
    titles = [_title(b) for b in buttons]
    want = ['gh-cli', 'reddit-cli', 'websearch', 'rag-cli', 'iterative-dev',
            'trading', 'trading_ai', 'monitor-cc', 'general', 'wise2627']
    assert titles == want, f'titles {titles}'
    assert list(_imp('launch_config').LAUNCH_PROJECTS) == _EXPECTED_PROJECTS
    return f'10 rows in order: {titles}'

def _case_start_command() -> str:
    sl = _imp('session_launch')
    for project in _EXPECTED_PROJECTS:
        want = (f'cd {_ROOT_DIR} && PATH="$HOME/.local/bin:$PATH" '
                f'./src/claude_proxy_start.sh --project {project}')
        got = sl._build_start_command(_ROOT_DIR, project)
        assert got == want, f'\nwant {want}\ngot  {got}'
    return f'10 commands match exactly, e.g. {sl._build_start_command(_ROOT_DIR, _EXPECTED_PROJECTS[0])}'

def _run_workflow(desktop, project, switch_effect=None, open_result=None):
    sl = _imp('session_launch')
    calls = []
    logs = []
    def switch(d):
        calls.append(('switch', d))
        return switch_effect(d) if switch_effect else 280.0
    def _open(cmd):
        calls.append(('open', cmd))
        return open_result or SimpleNamespace(returncode=0, stderr='')
    with patch.object(sl, 'switch_to_desktop_workflow', switch), \
         patch.object(sl, '_launch_monitor_ghostty_native', _open), \
         patch.object(sl, 'active_desktop_number', lambda: desktop), \
         patch.object(sl, 'MONITOR_CC_ROOT', _ROOT_DIR), \
         patch.object(sl.time, 'sleep', lambda s: calls.append(('sleep', s))), \
         patch.object(sl, 'log_menubar', lambda cat, msg: logs.append((cat, msg))):
        sl.launch_workflow(desktop, project)
    return calls, logs

def _case_workflow_success() -> str:
    project = _EXPECTED_PROJECTS[7]
    calls, logs = _run_workflow(3, project)
    kinds = [c[0] for c in calls]
    assert kinds == ['switch', 'sleep', 'open'], f'order {kinds}'
    assert calls[0] == ('switch', 3)
    assert calls[2][1] == (f'cd {_ROOT_DIR} && PATH="$HOME/.local/bin:$PATH" '
                           f'./src/claude_proxy_start.sh --project {project}')
    assert len(logs) == 1 and logs[0][0] == 'launch' and logs[0][1].startswith('OK desktop=3'), logs
    return f'order {kinds}; log: {logs[0][1]}'

def _case_workflow_failures() -> str:
    sw = _imp('space_switch')
    project = _EXPECTED_PROJECTS[0]
    out = []
    def _raise(exc):
        def f(d):
            raise exc
        return f
    for label, kwargs, want_stage in (
            ('postevent missing', dict(switch_effect=_raise(sw.SpaceSwitchError('postevent_not_granted'))), 'switch'),
            ('switch timeout', dict(switch_effect=_raise(sw.SpaceSwitchError('switch_timeout_3s'))), 'switch')):
        calls, logs = _run_workflow(2, project, **kwargs)
        assert [c[0] for c in calls] == ['switch'], f'{label}: calls {calls}'
        assert logs[0][1].startswith('FAILED') and f'stage={want_stage}' in logs[0][1], logs
        out.append(f'{label}: no window opened, {logs[0][1]}')
    calls, logs = _run_workflow(6, project)
    assert calls == [] and 'stage=validate' in logs[0][1] and logs[0][1].startswith('FAILED'), (calls, logs)
    out.append(f'desktop 6: {logs[0][1]}')
    calls, logs = _run_workflow(2, '/tmp/not-in-list')
    assert calls == [] and 'stage=validate' in logs[0][1], (calls, logs)
    out.append(f'unknown project: {logs[0][1]}')
    calls, logs = _run_workflow(2, project, open_result=SimpleNamespace(returncode=1, stderr='boom'))
    assert [c[0] for c in calls] == ['switch', 'sleep', 'open']
    assert logs[0][1].startswith('FAILED') and 'stage=open_window' in logs[0][1] and 'boom' in logs[0][1], logs
    out.append(f'osascript rc=1: {logs[0][1]}')
    return ' | '.join(out)

class _SyncThread:
    def __init__(self, target, args=(), daemon=None):
        self._t, self._a = target, args

    def start(self):
        self._t(*self._a)

def _case_click_handling() -> str:
    lc = _imp('launch_controller')
    app = _FakeApp([_session('a', 1)])
    ctl = lc.LaunchController(app)
    ctl.open()
    launched = []
    closed = []
    logs = []
    with patch.object(lc, 'launch_workflow', lambda d, p: launched.append((d, p))), \
         patch.object(lc, '_close_launch_panel', lambda a: closed.append(a)), \
         patch.object(lc.threading, 'Thread', _SyncThread), \
         patch.object(lc, 'log_menubar', lambda c, m: logs.append(m)):
        ctl.handle_launch_project(0)
        assert launched == [] and 'no_desktop_selected' in logs[-1], (launched, logs)
        ctl.handle_select_desktop(2)
        ctl._launch_in_progress = True
        ctl.handle_launch_project(0)
        assert launched == [] and 'launch_in_progress' in logs[-1], (launched, logs)
        ctl._launch_in_progress = False
        app.sessions.items = [_session('a', 1), _session('b', 2)]
        ctl.handle_launch_project(0)
        assert launched == [(2, _EXPECTED_PROJECTS[0])], f'occupied desktop not launched: {launched}'
        assert len(closed) == 1 and ctl._selected_desktop is None
        launched.clear()
        closed.clear()
        ctl.handle_select_desktop(4)
        ctl.handle_launch_project(9)
        assert launched == [(4, _EXPECTED_PROJECTS[9])], launched
        assert len(closed) == 1, 'panel not closed on launch'
        assert ctl._launch_in_progress is False and ctl._selected_desktop is None
        ctl.handle_select_desktop(5)
        ctl.handle_launch_project(10)
        assert len(launched) == 1 and 'index_out_of_range' in logs[-1], (launched, logs)
    return f'no desktop -> ignored; busy -> ignored; occupied desktop 2 -> launched; free desktop 4 -> launch{launched[0]}, panel closed; bad index ignored'

def _case_space_switch_units() -> str:
    sw = _imp('space_switch')
    out = []
    fake = MagicMock()
    fake.CGPreflightPostEventAccess.return_value = False
    fake.CGRequestPostEventAccess.return_value = False
    with patch.object(sw, '_CG', fake):
        try:
            sw._require_post_event_access()
            raise AssertionError('no error without PostEvent')
        except sw.SpaceSwitchError as exc:
            assert str(exc) == 'postevent_not_granted'
        assert fake.CGRequestPostEventAccess.call_count == 0, 'switch path must not request access'
        assert sw.request_post_event_access_if_missing() is False
        assert fake.CGRequestPostEventAccess.call_count == 1
    out.append('no PostEvent -> switch path raises without requesting; request function requests once and returns False')
    fake.CGPreflightPostEventAccess.return_value = True
    fake.CGRequestPostEventAccess.reset_mock()
    with patch.object(sw, '_CG', fake):
        sw._require_post_event_access()
        assert sw.request_post_event_access_if_missing() is True
    assert fake.CGRequestPostEventAccess.call_count == 0
    out.append('PostEvent granted -> no request, returns True')
    space_map = {3: ('D', 1), 4: ('D', 2), 5: ('D', 3), 6: ('D', 4), 7: ('D', 5)}
    fake.CGSMainConnectionID.return_value = 1
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: space_map):
        assert [sw._space_id_for_desktop(n) for n in range(1, 6)] == [3, 4, 5, 6, 7]
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: {3: ('D', 1)}):
        try:
            sw._space_id_for_desktop(4)
            raise AssertionError('missing desktop accepted')
        except sw.SpaceSwitchError as exc:
            assert 'desktop_4_space_matches=0' in str(exc)
    with patch.object(sw, '_CG', fake), patch.object(sw, '_build_space_map', lambda cid: {3: ('D', 1), 9: ('E', 1)}):
        try:
            sw._space_id_for_desktop(1)
            raise AssertionError('ambiguous desktop accepted')
        except sw.SpaceSwitchError as exc:
            assert 'desktop_1_space_matches=2' in str(exc)
    out.append('desktop -> space id for 1..5; missing and ambiguous desktop raise')
    keys = []
    with patch.object(sw, '_post_key', lambda kc, down: keys.append((kc, down))):
        for n in range(1, 6):
            sw._post_desktop_hotkey(n)
    assert keys == [(18, True), (18, False), (19, True), (19, False), (20, True), (20, False),
                    (21, True), (21, False), (23, True), (23, False)], keys
    out.append('hotkey key codes 18,19,20,21,23 down+up')
    seq = iter([1, 1, 4])
    with patch.object(sw, 'active_space_id', lambda: next(seq)), patch.object(sw.time, 'sleep', lambda s: None):
        ms = sw._wait_until_active(4)
    assert ms >= 0
    with patch.object(sw, 'active_space_id', lambda: 1), patch.object(sw, '_SWITCH_TIMEOUT', 0.05):
        try:
            sw._wait_until_active(4)
            raise AssertionError('timeout not raised')
        except sw.SpaceSwitchError as exc:
            assert 'switch_timeout' in str(exc)
    out.append('wait_until_active: returns on target, raises switch_timeout otherwise')
    return ' | '.join(out)

def _case_request_on_open() -> str:
    import threading
    lc = _imp('launch_controller')
    calls = []
    logs = []
    def request(granted):
        def f():
            calls.append(threading.current_thread().name)
            return granted
        return f
    ctl = lc.LaunchController(_FakeApp([]))
    with patch.object(lc, 'request_post_event_access_if_missing', request(False)), \
         patch.object(lc, 'log_menubar', lambda c, m: logs.append(m)):
        ctl.open()
    assert calls == [threading.main_thread().name], f'calls {calls}'
    assert len(logs) == 1 and 'postevent_not_granted' in logs[0] and 'main thread' in logs[0], logs
    calls.clear()
    logs.clear()
    with patch.object(lc, 'request_post_event_access_if_missing', request(True)), \
         patch.object(lc, 'log_menubar', lambda c, m: logs.append(m)):
        ctl.open()
    assert len(calls) == 1 and logs == [], (calls, logs)
    calls.clear()
    logs.clear()
    ctl.handle_select_desktop(2)
    with patch.object(lc, 'request_post_event_access_if_missing', request(False)), \
         patch.object(lc, 'launch_workflow', lambda d, p: None), \
         patch.object(lc, '_close_launch_panel', lambda a: None), \
         patch.object(lc.threading, 'Thread', _SyncThread):
        ctl.handle_launch_project(0)
    assert calls == [], f'click path requested access: {calls}'
    return 'open() requests once on the main thread and logs when missing; granted -> silent; click/launch path never requests'

_CASES = {
    'request_on_open': _case_request_on_open,
    'headers': _case_headers,
    'occupied_marking': _case_occupied_marking,
    'tick_and_selection': _case_tick_and_selection,
    'project_rows': _case_project_rows,
    'start_command': _case_start_command,
    'workflow_success': _case_workflow_success,
    'workflow_failures': _case_workflow_failures,
    'click_handling': _case_click_handling,
    'space_switch_units': _case_space_switch_units,
}

def _build_report(results) -> str:
    lines = ['# t2_launch_tab report', '', f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
             '- every case ran in its own subprocess, all cases in parallel', '',
             '| case | result | detail |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["name"]} | {"PASS" if r["ok"] else "FAIL"} | {r["detail"]} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(r["ok"] for r in results) else "FAIL"}')
    return '\n'.join(lines)

if __name__ == '__main__':
    main()
