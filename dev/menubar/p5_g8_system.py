# INFRASTRUCTURE
import ast
import errno
import json
import os
import subprocess
from unittest import mock

from p5_common import load, root, tmpdir, check, point_log, log_text, digest

_NEW = os.environ.get('P5_ROOT') is None

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    system = load('system')
    singleton_lock(system, d)
    python3_resolution(system, d, mlog)
    viewer_tty(system, mlog)
    skills(d, mlog)
    if _NEW:
        open_or_focus_guard_removed()

# FUNCTIONS

def singleton_lock(system, d) -> None:
    system._LOCK_PATH = d / 'menubar.pid'
    first = system._acquire_singleton_lock()
    second = system._acquire_singleton_lock()
    ok = first is not None and second is None
    print(f'DIFF singleton {digest((first is not None, second is None))}')
    check('g8.singleton.first_acquires_second_refused', ok)
    first.close()
    if not _NEW:
        return
    with mock.patch.object(system.fcntl, 'flock', side_effect=OSError(errno.EPERM, 'denied')):
        try:
            system._acquire_singleton_lock()
            propagated = False
        except OSError:
            propagated = True
    check('g8.singleton.non_lock_oserror_propagates', propagated)

def python3_resolution(system, d, mlog) -> None:
    resolved = system._resolve_launch_python3()
    print(f'DIFF python3 {digest(resolved)}')
    check('g8.python3.resolved_from_plist', resolved.endswith('python3') and os.path.exists(resolved))
    if not _NEW:
        return
    check('g8.python3.route_logged', 'route=plist' in log_text(mlog))
    system._PLIST_PATH = d / 'no_plist.plist'
    with mock.patch.dict(os.environ, {'PATH': '/nonexistent_p5'}):
        try:
            system._resolve_launch_python3()
            raised = False
        except RuntimeError as exc:
            raised = 'python3 not found' in str(exc) and 'plist unreadable' in str(exc)
    check('g8.python3.missing_raises', raised)
    called = []
    with mock.patch.dict(os.environ, {'PATH': '/nonexistent_p5'}), \
         mock.patch.object(system, '_launch_monitor_ghostty_native', lambda cmd: called.append(cmd)):
        system._launch_monitor('/some/cwd')
    check('g8.python3.launch_failure_logged_and_no_launch', not called and 'launch FAILED cwd=/some/cwd' in log_text(mlog))

def viewer_tty(system, mlog) -> None:
    ps = '10 ttys001 tmux attach -t worker-a\n11 ttys002 tmux attach-session -t worker-b\n12 ?? tmux attach -t worker-a\n13 ttys003 vim\n'
    with mock.patch.object(system.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 0, ps, '')):
        got = (system._find_worker_viewer_tty('worker-a'), system._find_worker_viewer_tty('worker-b'), system._find_worker_viewer_tty('worker-z'))
    print(f'DIFF viewer_tty {digest(got)}')
    check('g8.viewer_tty.normal', got == ('ttys001', 'ttys002', None))
    if not _NEW:
        return
    def boom(*a, **k):
        raise subprocess.TimeoutExpired('ps', 3)
    with mock.patch.object(system.subprocess, 'run', boom):
        r = system._find_worker_viewer_tty('worker-a')
    check('g8.viewer_tty.ps_failure_logged', r is None and 'ps failed' in log_text(mlog))

def skills(d, mlog) -> None:
    sd = load('skill_discovery')
    claude = d / 'claude'
    plug = d / 'plug'
    (plug / '.claude-plugin').mkdir(parents=True)
    (plug / 'skills' / 'alpha').mkdir(parents=True)
    (plug / 'skills' / 'alpha' / 'SKILL.md').write_text('no frontmatter here\n')
    (plug / 'skills' / 'beta').mkdir(parents=True)
    (plug / 'skills' / 'beta' / 'SKILL.md').write_text('---\nname: beta-named\n---\n')
    (plug / '.claude-plugin' / 'plugin.json').write_text(json.dumps({'name': 'pl', 'skills': ['skills/alpha', 'skills/beta']}))
    (claude / 'plugins').mkdir(parents=True)
    (claude / 'settings.json').write_text(json.dumps({'enabledPlugins': {'pl@m': True}}))
    (claude / 'plugins' / 'installed_plugins.json').write_text(json.dumps({'plugins': {'pl@m': [{'scope': 'local', 'installPath': str(plug)}]}}))
    got = sd.discover_skills_workflow('', claude)
    print(f'DIFF skills {digest(got)}')
    check('g8.skills.normal', [(s.short, s.full) for s in got] == [('alpha', 'pl:alpha'), ('beta-named', 'pl:beta-named')])
    if not _NEW:
        return
    text = log_text(mlog)
    check('g8.skills.fallback_routes_logged', 'no user-scope install entry' in text and 'skill=alpha has no frontmatter name' in text)

def open_or_focus_guard_removed() -> None:
    tree = ast.parse((root() / 'src' / 'menubar' / 'system.py').read_text())
    fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_open_or_focus_monitor'][0]
    check('g8.open_or_focus.dead_guard_removed', not any(isinstance(n, ast.If) and 'cwd' in ast.dump(n.test) for n in ast.walk(fn)))


if __name__ == '__main__':
    main()
