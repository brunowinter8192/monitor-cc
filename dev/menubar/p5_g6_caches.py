# INFRASTRUCTURE
import json
import os
import subprocess
from unittest import mock

from p5_common import load, tmpdir, check, point_log, log_text, digest

_NEW = os.environ.get('P5_ROOT') is None

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    ghostty_reads(mlog)
    bg_timer(mlog)
    orphans(mlog)
    proc_cache_refreshes(d, mlog)
    tmux_activity(mlog)
    proxy_mtime(d, mlog)
    ghostty_writes(d, mlog)
    demote_keeps_hook_status(mlog)

# FUNCTIONS

def run_result(stdout='', returncode=0, stderr=''):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)

def boom(*a, **k):
    raise subprocess.TimeoutExpired('x', 1)

def since(mlog, start) -> str:
    return log_text(mlog)[start:]

def ghostty_reads(mlog) -> None:
    g = load('ghostty')
    with mock.patch.object(g.subprocess, 'run', lambda *a, **k: run_result('1 /usr/bin/x\n77 /Applications/Ghostty.app/Contents/MacOS/ghostty\n')):
        pid = g._ghostty_pid()
    with mock.patch.object(g.subprocess, 'run', lambda *a, **k: run_result('5 77 ttys001\n6 77 ??\n7 1 ttys009\n')):
        ttys = g._ghostty_child_ttys('77')
    print(f'DIFF ghostty_reads {digest((pid, ttys))}')
    check('g6.ghostty.reads_normal', pid == '77' and ttys == ['ttys001'])
    if not _NEW:
        return
    start = len(log_text(mlog))
    with mock.patch.object(g.subprocess, 'run', boom):
        r = (g._ghostty_pid(), g._ghostty_child_ttys('77'), g._query_terminal_names(), g._query_single_terminal_id('m'))
    t = since(mlog, start)
    check('g6.ghostty.subprocess_failures_logged', r == (None, [], None, None) and all(k in t for k in ('ps failed', 'osascript names failed', 'single id failed')))
    g._ghostty_tty_to_id.clear()
    g._ghostty_tty_last_refresh = 0.0
    with mock.patch.object(g, '_ghostty_pid', lambda: '50'), mock.patch.object(g, '_ghostty_child_ttys', lambda p: ['ttys1']), \
         mock.patch.object(g, '_write_markers', lambda t: [('ttys1', '__GHT_a')]), mock.patch.object(g, '_clear_markers', lambda m: None), \
         mock.patch.object(g.time, 'sleep', lambda s: None), \
         mock.patch.object(g, '_query_terminal_names', lambda: run_result('ID1|||__GHT_a\n')):
        g._refresh_ghostty_tty_to_id(100.0)
    ok = g._ghostty_tty_to_id == {'ttys1': 'ID1'}
    g._ghostty_tty_to_id.clear()
    g._ghostty_tty_last_refresh = 0.0
    start = len(log_text(mlog))
    with mock.patch.object(g, '_ghostty_pid', lambda: '50'), mock.patch.object(g, '_ghostty_child_ttys', lambda p: ['ttys1']), \
         mock.patch.object(g, '_write_markers', lambda t: [('ttys1', '__GHT_a')]), mock.patch.object(g, '_clear_markers', lambda m: None), \
         mock.patch.object(g.time, 'sleep', lambda s: None), \
         mock.patch.object(g, '_query_terminal_names', lambda: run_result('', 1, 'no permission')):
        g._refresh_ghostty_tty_to_id(100.0)
    check('g6.ghostty.refresh_flow_and_osascript_rc_logged', ok and 'osascript rc=1' in since(mlog, start))

def bg_timer(mlog) -> None:
    b = load('bg_timer')
    b._cc_proc_cache.clear()
    b._cc_proc_cache['100'] = ('ttys1', '/proj')
    ps = ('100 1 05:00 claude\n201 100 00:10 worker-cli wait --timeout 600\n202 300 00:05 sleep 30\n300 100 00:20 sh -c sleep 30 && echo done\n'
          '203 100 xx:yy sleep 5\n')
    with mock.patch.object(b.subprocess, 'run', lambda *a, **k: run_result(ps)):
        scan = b._scan_bg_sleep_timers({'/proj': 'proj'})
    etimes = (b._parse_etime('1-02:03:04'), b._parse_etime('05:00'))
    with mock.patch.object(b.subprocess, 'run', lambda *a, **k: run_result('p9\nn/tmp/a.output\n')):
        out = b._resolve_pid_output_file(9)
    print(f'DIFF bg_timer {digest((sorted(scan.items()), etimes, out))}')
    check('g6.bg_timer.normal', scan['proj'].sleep_pids == [201, 202] and etimes == (93784, 300) and out == '/tmp/a.output')
    if not _NEW:
        return
    check('g6.bg_timer.bad_etime_logged', log_text(mlog).count("unparseable etime='xx:yy'") == 1)
    start = len(log_text(mlog))
    with mock.patch.object(b.subprocess, 'run', boom):
        r = (b._scan_bg_sleep_timers({}), b._resolve_pid_output_file(9))
    t = since(mlog, start)
    check('g6.bg_timer.subprocess_failures_logged', r == ({}, None) and 'ps failed' in t and 'lsof failed pid=9' in t)
    f = b.Path(b.__file__).parent
    start = len(log_text(mlog))
    with mock.patch.object(b, '_resolve_pid_output_file', lambda pid: '/nonexistent_dir_p5/x.output'), \
         mock.patch.object(b.os, 'kill', lambda pid, sig: None), \
         mock.patch.object(b.Path, 'is_file', lambda self: True), \
         mock.patch.object(b.Path, 'stat', lambda self: mock.Mock(st_size=0)), \
         mock.patch.object(b.Path, 'write_text', mock.Mock(side_effect=OSError('read-only'))):
        b._abort_bg_sleep_timers([12345])
    check('g6.bg_timer.stamp_error_in_menubar_log', 'stamp write error file=/nonexistent_dir_p5/x.output' in since(mlog, start))

def orphans(mlog) -> None:
    o = load('bg_task_orphans')
    with mock.patch.object(o.subprocess, 'run', lambda *a, **k: run_result('  1  0\n 55  1\nbad\n')):
        m = o._build_ppid_map()
    print(f'DIFF orphans {digest(sorted(m.items()))}')
    check('g6.orphans.ppid_map_normal', m == {'1': '0', '55': '1'})
    if not _NEW:
        return
    start = len(log_text(mlog))
    with mock.patch.object(o.subprocess, 'run', boom):
        m2 = o._build_ppid_map()
    check('g6.orphans.ps_failure_logged', m2 == {} and 'ps failed' in since(mlog, start))

def proc_cache_refreshes(d, mlog) -> None:
    p = load('proc_cache')
    tasks = d / 'tasks'
    tasks.mkdir()
    p._TASKS_BASE = tasks
    p._bg_task_last_refresh = 0.0
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('p123\nn/x/tasks/a.output\np9\nn/x/other.txt\n')):
        p._refresh_bg_task_cache(100.0)
    p._cc_proc_cache.clear()
    p._cc_proc_last_refresh = 0.0
    def fake_run(cmd, **k):
        if cmd[0] == 'ps':
            return run_result('  PID TTY COMM\n100 ttys001 /usr/bin/claude\n101 ?? claude\n102 ttys002 vim\n')
        return run_result('COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\nclaude 100 u cwd DIR 1,1 1 2 /the/cwd\n')
    with mock.patch.object(p.subprocess, 'run', fake_run):
        p._refresh_cc_proc_cache(100.0)
    p._tmux_state_last_refresh = 0.0
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('a\nb\n')):
        p._refresh_tmux_state(100.0)
    tmux_ok = set(p._tmux_state_cache)
    p._tmux_state_last_refresh = 0.0
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('', 1, 'no server running')):
        p._refresh_tmux_state(200.0)
    tmux_rc = set(p._tmux_state_cache)
    p._tmux_state_cache = {'keep'}
    p._tmux_state_last_refresh = 0.0
    with mock.patch.object(p.subprocess, 'run', boom):
        p._refresh_tmux_state(300.0)
    tmux_exc = set(p._tmux_state_cache)
    active = p._has_active_bg('x', 's') 
    print(f'DIFF proc_cache {digest((sorted(p._bg_task_open_paths), p._bg_task_holder_pids, dict(p._cc_proc_cache), sorted(tmux_ok), sorted(tmux_rc), sorted(tmux_exc), active))}')
    check('g6.proc_cache.normal', p._cc_proc_cache == {'100': ('ttys001', '/the/cwd')} and tmux_ok == {'a', 'b'} and tmux_rc == set() and tmux_exc == {'keep'})
    if not _NEW:
        return
    load('menubar_log')._last_by_key.clear()
    start = len(log_text(mlog))
    p._bg_task_last_refresh = 0.0
    p._cc_proc_last_refresh = 0.0
    p._tmux_state_last_refresh = 0.0
    with mock.patch.object(p.subprocess, 'run', boom):
        p._refresh_bg_task_cache(1000.0)
        p._refresh_cc_proc_cache(1000.0)
        p._refresh_tmux_state(1000.0)
    t = since(mlog, start)
    check('g6.proc_cache.subprocess_failures_logged', all(k in t for k in ('lsof +D failed', 'ps failed', 'tmux list-sessions failed')))
    p._tmux_state_last_refresh = 0.0
    load('menubar_log')._last_by_key.clear()
    start = len(log_text(mlog))
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('', 1, 'no server running')):
        p._refresh_tmux_state(2000.0)
    check('g6.proc_cache.tmux_rc_logged', 'tmux list-sessions rc=1' in since(mlog, start))
    p._cc_proc_last_refresh = 0.0
    p._cc_proc_cache.clear()
    calls = []
    def flaky(cmd, **k):
        if cmd[0] == 'ps':
            return run_result('  PID TTY COMM\n100 ttys001 claude\n')
        raise subprocess.TimeoutExpired('lsof', 2)
    start = len(log_text(mlog))
    with mock.patch.object(p.subprocess, 'run', flaky):
        p._refresh_cc_proc_cache(3000.0)
    check('g6.proc_cache.per_pid_lsof_failure_logged', 'lsof cwd failed pid=100' in since(mlog, start))
    import ast, inspect
    src = inspect.getsource(p._has_active_bg)
    check('g6.proc_cache.dead_handler_removed', not any(isinstance(n, ast.Try) for n in ast.walk(ast.parse(src))))

def tmux_activity(mlog) -> None:
    p = load('proc_cache')
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('1700000000\n')):
        ok = p._tmux_window_activity('s')
    print(f'DIFF tmux_activity_ok {digest(ok)}')
    check('g6.tmux_activity.normal', ok == 1700000000)
    if not _NEW:
        return
    start = len(log_text(mlog))
    with mock.patch.object(p.subprocess, 'run', lambda *a, **k: run_result('', 1)):
        rc = p._tmux_window_activity('s2')
    with mock.patch.object(p.subprocess, 'run', boom):
        exc = p._tmux_window_activity('s3')
    t = since(mlog, start)
    check('g6.tmux_activity.failure_is_none_and_logged', rc is None and exc is None and 'display-message rc=1 session=s2' in t and 'activity failed session=s3' in t)

def proxy_mtime(d, mlog) -> None:
    p = load('proc_cache')
    logs = d / 'plogs'
    logs.mkdir()
    for name, mt in (('api_requests_a_opus_projx_1.jsonl', 5000), ('api_requests_b_opus_projx_2.jsonl', 6000), ('api_requests_c_opus_other_1.jsonl', 9000)):
        (logs / name).write_text('x')
        os.utime(logs / name, (mt, mt))
    p._PROXY_LOG_DIR = logs
    p._proxy_log_mtime_cache.clear()
    got = p._proxy_log_newest_mtime('projx', 100.0)
    print(f'DIFF proxy_mtime {digest(got)}')
    check('g6.proxy_mtime.normal', got == 6000)
    if not _NEW:
        return
    p._PROXY_LOG_DIR = d / 'absent'
    p._proxy_log_mtime_cache.clear()
    start = len(log_text(mlog))
    got = p._proxy_log_newest_mtime('projx', 100.0)
    check('g6.proxy_mtime.missing_dir_logged', got is None and 'proxy log dir missing' in since(mlog, start))
    p._PROXY_LOG_DIR = logs
    p._proxy_log_mtime_cache.clear()
    start = len(log_text(mlog))
    with mock.patch.object(p.Path, 'stat', mock.Mock(side_effect=OSError('vanished'))):
        gone = p._proxy_log_newest_mtime('projx', 100.0)
    check('g6.proxy_mtime.stat_failure_logged', gone is None and 'stat failed file=api_requests_a_opus_projx_1.jsonl' in since(mlog, start))
    paths = load('paths')
    check('g6.proxy_mtime.default_derives_from_root', str(p.MONITOR_CC_ROOT) == str(paths.MONITOR_CC_ROOT))

def ghostty_writes(d, mlog) -> None:
    g = load('ghostty')
    writes = []
    fake_open = mock.mock_open()
    with mock.patch('builtins.open', fake_open):
        g._write_markers(['ttys7'])
        g._clear_markers([('ttys7', 'm')])
    normal = [c.args[0] for c in fake_open().write.call_args_list]
    print(f'DIFF marker_writes {digest([x if isinstance(x, bytes) and b"__GHT_" not in x else b"marker" for x in normal])}')
    check('g6.ghostty.marker_writes_normal', len(normal) == 2 and normal[1] == b'\033]2;\007')
    g._APP_SUPPORT = d
    g._cc_proc_cache.clear()
    g._cc_proc_cache['1'] = ('ttys7', '/c')
    g._ghostty_tty_to_id.clear()
    g._ghostty_tty_to_id['ttys7'] = 'U1'
    g._ghostty_cwd_uuid_last = {}
    g._write_cwd_uuid_map()
    written = (d / 'ghostty_cwd_uuid.json').read_text()
    print(f'DIFF cwd_uuid {digest(written)}')
    check('g6.ghostty.cwd_uuid_written', json.loads(written) == {'/c': 'U1'})
    if not _NEW:
        return
    start = len(log_text(mlog))
    with mock.patch.object(g, 'open', mock.Mock(side_effect=OSError('no tty')), create=True):
        g._write_markers(['ttyX'])
        g._clear_markers([('ttyX', 'm')])
    t = since(mlog, start)
    check('g6.ghostty.marker_failures_logged', 'marker write failed tty=ttyX' in t and 'marker clear failed tty=ttyX' in t)
    blocker = d / 'blocker'
    blocker.write_text('x')
    g._APP_SUPPORT = blocker / 'sub'
    g._ghostty_cwd_uuid_last = {}
    start = len(log_text(mlog))
    g._write_cwd_uuid_map()
    check('g6.ghostty.cwd_uuid_failure_logged', 'cwd uuid map write failed' in since(mlog, start))

def demote_keeps_hook_status(mlog) -> None:
    if not _NEW:
        return
    disc = load('discover')
    disc._cwd_from_jsonl = lambda p: '/U/P/.claude/worktrees/a'
    disc._tmux_session_exists = lambda s: True
    disc._tmux_window_activity = lambda s: None
    hook = {'s': {'status': 'working', 'updated_ts': 999.0}}
    jl = mock.Mock(stem='s')
    info = disc._worker_session_info(jl, 990.0, 'e', 'P', 'a', 's', False, hook, 1000.0)
    check('g6.discover.unknown_activity_keeps_hook_status', info.status == 'working')


if __name__ == '__main__':
    main()
