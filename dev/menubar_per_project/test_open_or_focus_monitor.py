#!/usr/bin/env python3
# INFRASTRUCTURE
import importlib
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

_system_mod = importlib.import_module('src.menubar.system')
_tmux_launcher_mod = importlib.import_module('src.tmux_launcher')

# ORCHESTRATOR

def test_open_or_focus_monitor_workflow() -> None:
    failures = []
    _test_session_name_reused_not_rederived(failures)
    _test_launch_cmd_quotes_cwd_with_space(failures)
    _test_existing_session_killed_then_relaunched(failures)
    _test_branch_launches_when_session_absent(failures)
    _test_empty_cwd_is_noop(failures)
    _test_resolve_python3_uses_plist_path_under_bare_environ(failures)
    _test_launch_monitor_uses_native_path_only(failures)
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")

# FUNCTIONS

def _check(failures: list, desc: str, ok: bool, detail: str) -> None:
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {desc}: {detail}")
    if not ok:
        failures.append(desc)

def _test_session_name_reused_not_rederived(failures: list) -> None:
    cwd = '/tmp/some project'
    expected = _tmux_launcher_mod.generate_session_name(cwd)
    _check(failures, 'system.generate_session_name IS tmux_launcher.generate_session_name',
          _system_mod.generate_session_name is _tmux_launcher_mod.generate_session_name,
          f'{_system_mod.generate_session_name!r}')
    _check(failures, 'session name for a cwd with a space matches tmux_launcher exactly',
          _system_mod.generate_session_name(cwd) == expected,
          f'got={_system_mod.generate_session_name(cwd)!r} expected={expected!r}')
    _check(failures, 'session name has the monitor_cc_<8-hex> shape',
          expected.startswith('monitor_cc_') and len(expected) == len('monitor_cc_') + 8,
          f'name={expected!r}')

def _test_launch_cmd_quotes_cwd_with_space(failures: list) -> None:
    root = Path('/Users/x/monitor-cc')
    py3 = '/opt/homebrew/bin/python3'
    cwd = '/tmp/my project; rm -rf /'
    cmd = _system_mod._build_monitor_launch_cmd(root, py3, cwd)
    cd_part, run_part = cmd.split(' && ', 1)
    parsed = shlex.split(run_part)
    _check(failures, 'cd target is the given root, shell-quoted',
          cd_part == f'cd {shlex.quote(str(root))}', f'cd_part={cd_part!r}')
    _check(failures, 'cwd survives shlex round-trip as exactly one argument (not split/executed)',
          parsed == [py3, 'workflow.py', '--project', cwd], f'parsed={parsed!r}')

def _test_existing_session_killed_then_relaunched(failures: list) -> None:
    calls = _run_open_or_focus_monitor_with_stubs(session_exists=True, cwd='/tmp/existing-project')
    expected_name = _tmux_launcher_mod.generate_session_name('/tmp/existing-project')
    _check(failures, 'existing session → kill_session called with the derived session name',
          calls['kill'] == expected_name, f'calls={calls!r}')
    _check(failures, 'existing session → _launch_monitor called with the row cwd afterwards',
          calls['launch'] == '/tmp/existing-project', f'calls={calls!r}')

def _test_branch_launches_when_session_absent(failures: list) -> None:
    calls = _run_open_or_focus_monitor_with_stubs(session_exists=False, cwd='/tmp/new-project')
    _check(failures, 'no session → _launch_monitor called with the row cwd',
          calls['launch'] == '/tmp/new-project', f'calls={calls!r}')
    _check(failures, 'no session → kill_session NOT called',
          calls['kill'] is None, f'calls={calls!r}')

def _test_empty_cwd_is_noop(failures: list) -> None:
    calls = _run_open_or_focus_monitor_with_stubs(session_exists=True, cwd='')
    _check(failures, 'empty cwd short-circuits before any tmux/kill/launch call',
          calls == {'checked': None, 'kill': None, 'launch': None}, f'calls={calls!r}')

def _test_resolve_python3_uses_plist_path_under_bare_environ(failures: list) -> None:
    bare_env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
    repo_root = Path(__file__).resolve().parent.parent.parent
    r = subprocess.run(
        [sys.executable, '-c',
         "import importlib; m = importlib.import_module('src.menubar.system'); "
         "print(m._resolve_launch_python3())"],
        cwd=str(repo_root), env=bare_env, capture_output=True, text=True, timeout=10)
    resolved = r.stdout.strip()
    _check(failures, 'python3 resolved under a bare (no-Homebrew) PATH is still the Homebrew one',
          resolved.startswith('/opt/homebrew/') or resolved.startswith('/usr/local/'),
          f'resolved={resolved!r} stderr={r.stderr.strip()!r}')

def _test_launch_monitor_uses_native_path_only(failures: list) -> None:
    _check(failures, '_ghostty_version removed from system.py',
          not hasattr(_system_mod, '_ghostty_version'),
          f'hasattr={hasattr(_system_mod, "_ghostty_version")}')
    _check(failures, '_launch_monitor_ghostty_fallback removed from system.py',
          not hasattr(_system_mod, '_launch_monitor_ghostty_fallback'),
          f'hasattr={hasattr(_system_mod, "_launch_monitor_ghostty_fallback")}')

    class _FakeResult:
        returncode = 0
        stderr = ''

    calls = {'native': None}
    orig = _system_mod._launch_monitor_ghostty_native
    _system_mod._launch_monitor_ghostty_native = (
        lambda shell_cmd: calls.__setitem__('native', shell_cmd) or _FakeResult())
    try:
        _system_mod._launch_monitor('/tmp/native-path-project')
    finally:
        _system_mod._launch_monitor_ghostty_native = orig
    _check(failures, '_launch_monitor calls _launch_monitor_ghostty_native unconditionally',
          calls['native'] is not None and '/tmp/native-path-project' in calls['native'],
          f'calls={calls!r}')

def _run_open_or_focus_monitor_with_stubs(session_exists: bool, cwd: str) -> dict:
    calls = {'checked': None, 'kill': None, 'launch': None}
    orig = (_system_mod.check_session_exists, _system_mod.kill_session, _system_mod._launch_monitor)
    _system_mod.check_session_exists = lambda name: calls.__setitem__('checked', name) or session_exists
    _system_mod.kill_session = lambda name: calls.__setitem__('kill', name)
    _system_mod._launch_monitor = lambda c: calls.__setitem__('launch', c)
    try:
        _system_mod._open_or_focus_monitor(cwd)
    finally:
        (_system_mod.check_session_exists, _system_mod.kill_session,
         _system_mod._launch_monitor) = orig
    return calls


if __name__ == '__main__':
    test_open_or_focus_monitor_workflow()
