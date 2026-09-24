# INFRASTRUCTURE
from types import SimpleNamespace
from unittest.mock import patch

from dev.session_launcher.t2_fixtures import _EXPECTED_PROJECTS, _ROOT_DIR, _imp

# FUNCTIONS

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
