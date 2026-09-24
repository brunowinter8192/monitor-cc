# INFRASTRUCTURE
import ast
import json
from unittest import mock

from p5_common import load, root, tmpdir, check, point_log, log_text, digest

_NOW = 1_000_000.0

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    disc = load('discover')
    cwd_from_jsonl(disc, d, mlog)
    worker_and_main_sessions(disc, mlog)
    if hasattr(disc, '_log_routes'):
        route_logs(disc, mlog)
        project_loop(disc, mlog)
        worker_loop(mlog)
        panel_guard_removed()

# FUNCTIONS

class _Dir:
    def __init__(self, name):
        self.name = name

class _Jsonl:
    def __init__(self, stem, mtime):
        self.stem, self._m = stem, mtime
    def stat(self):
        return mock.Mock(st_mtime=self._m)

def cwd_from_jsonl(disc, d, mlog) -> None:
    f = d / 's.jsonl'
    f.write_text('ial": "cut off first line"}\n' + json.dumps({'type': 'x'}) + '\n[1,2]\n' + json.dumps({'cwd': '/p/q'}) + '\n')
    got = disc._cwd_from_jsonl(f)
    empty = d / 'e.jsonl'
    empty.write_text('')
    print(f'DIFF cwd_from_jsonl {digest((got, disc._cwd_from_jsonl(empty)))}')
    check('g5.cwd_from_jsonl.normal', got == '/p/q' and disc._cwd_from_jsonl(empty) is None)
    if hasattr(disc, '_log_routes'):
        missing = d / 'missing.jsonl'
        check('g5.cwd_from_jsonl.oserror_logged', disc._cwd_from_jsonl(missing) is None and 'cwd read failed' in log_text(mlog))

def worker_and_main_sessions(disc, mlog) -> None:
    disc._cwd_from_jsonl = lambda p: '/Users/x/Proj/.claude/worktrees/alpha'
    disc._tmux_session_exists = lambda s: True
    disc._tmux_window_activity = lambda s: _NOW - 2
    disc._proc_cwd_for_encoded_dir = lambda e: '/Users/x/Proj/'
    disc._proxy_log_newest_mtime = lambda k, n: _NOW - 1
    hook = {'sw': {'status': 'working', 'updated_ts': _NOW - 1}}
    w = disc._worker_session_info(_Jsonl('sw', _NOW - 5), _NOW - 5, 'enc-w', 'Proj', 'alpha', 'sw', False, hook, _NOW)
    w_nohook = disc._worker_session_info(_Jsonl('sx', _NOW - 5), _NOW - 5, 'enc-w', 'Proj', 'alpha', 'sx', False, {}, _NOW)
    disc._tmux_window_activity = lambda s: 0
    w_demote = disc._worker_session_info(_Jsonl('sw', _NOW - 5), _NOW - 5, 'enc-w', 'Proj', 'alpha', 'sw', False, hook, _NOW)
    disc._cwd_from_jsonl = lambda p: None
    w_mtime = disc._worker_session_info(_Jsonl('sy', _NOW - 5), _NOW - 5, 'enc-w', 'Proj', 'alpha', 'sy', True, {}, _NOW)
    m_hook = disc._main_session_info('enc-m', 'sm', False, {'sm': {'status': 'idle', 'updated_ts': _NOW - 1}}, _NOW - 500, _NOW)
    m_mtime = disc._main_session_info('enc-m', 'sm2', True, {}, _NOW - 5, _NOW)
    m_proxy = disc._main_session_info('enc-m', 'sm3', False, {}, _NOW - 500, _NOW)
    disc._proxy_log_newest_mtime = lambda k, n: None
    m_idle = disc._main_session_info('enc-m', 'sm4', False, {}, _NOW - 500, _NOW)
    results = [w, w_nohook, w_demote, w_mtime, m_hook, m_mtime, m_proxy, m_idle]
    print(f'DIFF sessions {digest(results)}')
    check('g5.sessions.statuses',
          [r.status for r in results] == ['working', 'idle', 'idle', 'idle', 'idle', 'working', 'working', 'idle']
          and results[0].name == 'alpha' and results[4].name == 'Proj' and results[4].cwd == '/Users/x/Proj/')

def route_logs(disc, mlog) -> None:
    text = log_text(mlog)
    need = ['alive_route=tmux status_route=hook', 'status_route=hook_tmux_demote', 'alive_route=mtime status_route=no_fresh_hook',
            'alive_route=process status_route=mtime', 'status_route=proxy_override', 'alive_route=process status_route=hook']
    check('g5.routes.logged', all(n in text for n in need))
    before = log_text(mlog)
    disc._main_session_info('enc-m', 'sm', False, {'sm': {'status': 'idle', 'updated_ts': _NOW - 1}}, _NOW - 500, _NOW)
    check('g5.routes.unchanged_route_silent', log_text(mlog) == before)

def project_loop(disc, mlog) -> None:
    for n in ('_refresh_cc_proc_cache', '_refresh_ghostty_tty_to_id', '_refresh_tmux_state', '_refresh_bg_task_cache', '_read_hook_state', '_write_cwd_uuid_map'):
        setattr(disc, n, lambda *a, **k: None)
    disc.detect_main_desktop_numbers = lambda *a, **k: {}
    disc.get_project_directories = lambda: [_Dir('bad'), _Dir('good')]
    good = disc.SessionInfo('g', 'idle', False, 'good', 'g', False, '/g', 'sg', '')
    def proc(project_dir, now):
        if project_dir.name == 'bad':
            raise RuntimeError('dir broken')
        return good
    disc._process_project_dir = proc
    r1 = disc.list_alive_sessions()
    r2 = disc.list_alive_sessions()
    text = log_text(mlog)
    check('g5.project_loop.skipped_logged_once_others_kept', [s.name for s in r1] == ['g'] and len(r2) == 1 and text.count('project skipped dir=bad') == 1)
    disc._process_project_dir = lambda pd, now: good
    disc.list_alive_sessions()
    disc._process_project_dir = proc
    disc.list_alive_sessions()
    check('g5.project_loop.recovery_rearms_log', log_text(mlog).count('project skipped dir=bad') == 2)

class _Stop(BaseException):
    pass

def worker_loop(mlog) -> None:
    dw = load('discovery_worker')
    def run_one_cycle():
        with mock.patch.object(dw.time, 'sleep', side_effect=_Stop):
            try:
                dw._worker_loop()
            except _Stop:
                pass
    with mock.patch.object(dw, 'list_alive_sessions', side_effect=RuntimeError('cycle broke')):
        run_one_cycle()
        run_one_cycle()
    check('g5.worker_loop.error_logged_once', log_text(mlog).count('worker cycle error err=RuntimeError') == 1)
    with mock.patch.object(dw, 'list_alive_sessions', return_value=[]), \
         mock.patch.object(dw, '_scan_bg_sleep_timers', return_value={}), \
         mock.patch.object(dw, 'scan_bg_task_orphans'):
        run_one_cycle()
        check('g5.worker_loop.success_publishes_snapshot', dw.get_latest_snapshot().sessions == [])
    with mock.patch.object(dw, 'list_alive_sessions', side_effect=RuntimeError('cycle broke')):
        run_one_cycle()
    check('g5.worker_loop.recovery_rearms_log', log_text(mlog).count('worker cycle error err=RuntimeError') == 2)

def panel_guard_removed() -> None:
    tree = ast.parse((root() / 'src' / 'menubar' / 'panel.py').read_text())
    fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_reposition_tab_panel'][0]
    check('g5.panel.reposition_guard_removed', not any(isinstance(n, ast.If) for n in ast.walk(fn)))


if __name__ == '__main__':
    main()
