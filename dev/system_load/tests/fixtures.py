# INFRASTRUCTURE
_UID = 501
_HOME = '/Users/brunowinter2000'
_CC_BIN = f'{_HOME}/cc-cache-fix-280/node_modules/@anthropic-ai/claude-code/bin/claude.exe'
_PYTHON_APP = '/opt/homebrew/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python'
_UNSET = object()
_LSTART = 'Fri Sep 25 18:17:10 2026'
_TASKS = '/private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/00000000-0000-0000-0000-000000000000/tasks'
CC_BIN = _CC_BIN
PYTHON_APP = _PYTHON_APP
TASKS = _TASKS
HOME = _HOME


# FUNCTIONS

def proc(pid, ppid, command, uid=_UID, tty='??', age_s=600.0, cpu_s=5.0, rss_kb=20000, lstart=None):
    return {
        'pid': pid, 'ppid': ppid, 'uid': uid, 'tty': tty, 'age_s': age_s, 'cpu_s': cpu_s,
        'rss_kb': rss_kb, 'stat': 'S', 'lstart': lstart or f'{_LSTART[:-5]}{pid % 60:02d} 2026', 'command': command,
    }


def snapshot(procs, self_pid, sessions=None, panes=None, cpu_now=None, task_files=None,
             established=_UNSET, cwds=None, tmux_ok=True, protect_pids=None, protect_roots=None):
    return {
        'taken_at': 1790354000.0, 'self_pid': self_pid, 'uid': _UID,
        'procs': procs, 'cwds': cwds or {}, 'cpu_now': cpu_now or {},
        'tmux': {'ok': tmux_ok, 'sessions': [{'name': n, 'created': c} for n, c in (sessions or [])],
                 'panes': [{'session': s, 'pane_pid': p, 'path': '/tmp'} for s, p in (panes or [])]},
        'task_files': task_files or [], 'established': [] if established is _UNSET else established,
        'system': {'load': [4.8, 5.4, 5.2], 'mem_free_pct': 63, 'swap_used_mb': 536.75, 'ncpu': 14},
        'protect_pids': protect_pids or [], 'protect_roots': protect_roots or [],
    }


def base_procs():
    return [
        proc(1, 0, '/sbin/launchd', uid=0),
        proc(864, 1, '/Applications/Ghostty.app/Contents/MacOS/ghostty'),
        proc(72039, 1, 'tmux new-session -d -s monitor_cc_5dd99b09 python3 workflow.py --mode tokens'),
        proc(9000, 864, '/bin/zsh'),
        proc(9001, 9000, _CC_BIN + ' --model claude-sonnet-5'),
        proc(9002, 9001, '/bin/zsh -c source snapshot.sh && python3 -m sysload snapshot'),
        proc(9003, 9002, 'python3 -m sysload snapshot'),
    ]


def by_pid(result):
    return {r['pid']: r for r in result['rows']}
