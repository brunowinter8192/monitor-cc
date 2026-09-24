# INFRASTRUCTURE
import importlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from dev.session_launcher.t2_fixtures import _EXPECTED_PROJECTS, _FakeApp, _SyncThread, _header_text, _imp, _session, _title

_EXPECTED_HEADERS = {
    'sessions': '[Sessions] · RAG · Models · Launch',
    'rag': 'Sessions · [RAG] · Models · Launch',
    'models': 'Sessions · RAG · [Models] · Launch',
    'launch': 'Sessions · RAG · Models · [Launch]',
}

# FUNCTIONS

def _case_headers() -> str:
    app = _FakeApp([])
    got = {}
    pm = _imp('panel_manager').PanelManager(app)
    pm.rebuild([])
    got['sessions'] = _header_text(pm._widgets.header_view)
    rag = _imp('rag_controller').RagController(app)
    rag.rebuild()
    got['rag'] = _header_text(rag._rag_header)
    models = _imp('model_controller').ModelController(app)
    models.rebuild()
    got['models'] = _header_text(models._models_header)
    launch = _imp('launch_controller').LaunchController(app)
    launch.open()
    got['launch'] = _header_text(launch._launch_header)
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

def _case_log_isolation() -> str:
    home = Path(os.environ['HOME'])
    paths = importlib.import_module('src.menubar.paths')
    log_mod = importlib.import_module('src.menubar.menubar_log')
    assert str(log_mod.MENUBAR_LOG).startswith(str(home)), f'log path {log_mod.MENUBAR_LOG}'
    for name in ('SETTINGS_FILE', 'HOOKS_FILE', 'PID_FILE', 'MONITOR_SWEEP_STATE_FILE'):
        assert str(getattr(paths, name)).startswith(str(home)), f'{name} {getattr(paths, name)}'
    lc = _imp('launch_controller')
    ctl = lc.LaunchController(_FakeApp([]))
    ctl.handle_select_desktop(7)
    text = log_mod.MENUBAR_LOG.read_text()
    assert 'reason=not_a_launch_desktop' in text, f'log text {text!r}'
    return f'launch log line landed in <home>/{log_mod.MENUBAR_LOG.relative_to(home)}'
