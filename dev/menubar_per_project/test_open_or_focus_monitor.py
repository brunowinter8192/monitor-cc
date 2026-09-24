#!/usr/bin/env python3
# INFRASTRUCTURE
import importlib
import os
import shlex
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dev.refactoring.strand_runner import strand_workflow

_system_mod = importlib.import_module('src.menubar.system')
_tmux_launcher_mod = importlib.import_module('src.tmux_launcher')

_STRAND_NAMES = [
    '_test_session_name_reused_not_rederived',
    '_test_launch_cmd_quotes_cwd_with_space',
    '_test_existing_session_killed_then_relaunched',
    '_test_branch_launches_when_session_absent',
    '_test_resolve_python3_uses_plist_path_under_bare_environ',
    '_test_launch_monitor_uses_native_path_only',
]
_TITLE = 'test_open_or_focus_monitor'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'test_open_or_focus_monitor.md'
_BARE_PATH = '/usr/bin:/bin:/usr/sbin:/sbin'
_FIXTURE_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>EnvironmentVariables</key><dict>
<key>PATH</key><string>{path}</string>
</dict></dict></plist>
"""
_RESOLVE_SNIPPET = (
    "import importlib, pathlib, sys; "
    "m = importlib.import_module('src.menubar.system'); "
    "m._PLIST_PATH = pathlib.Path(sys.argv[1]); "
    "print(m._resolve_launch_python3())"
)

# ORCHESTRATOR

def test_open_or_focus_monitor_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS

def _check(desc: str, ok: bool, detail: str) -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {desc}: {detail}")
    if not ok:
        raise AssertionError(desc)

def _test_session_name_reused_not_rederived() -> None:
    cwd = '/tmp/some project'
    expected = _tmux_launcher_mod.generate_session_name(cwd)
    _check('system.generate_session_name IS tmux_launcher.generate_session_name',
          _system_mod.generate_session_name is _tmux_launcher_mod.generate_session_name,
          f'{_system_mod.generate_session_name!r}')
    _check('session name for a cwd with a space matches tmux_launcher exactly',
          _system_mod.generate_session_name(cwd) == expected,
          f'got={_system_mod.generate_session_name(cwd)!r} expected={expected!r}')
    _check('session name has the monitor_cc_<8-hex> shape',
          expected.startswith('monitor_cc_') and len(expected) == len('monitor_cc_') + 8,
          f'name={expected!r}')

def _test_launch_cmd_quotes_cwd_with_space() -> None:
    root = Path('/Users/x/monitor-cc')
    py3 = '/opt/homebrew/bin/python3'
    cwd = '/tmp/my project; rm -rf /'
    cmd = _system_mod._build_monitor_launch_cmd(root, py3, cwd)
    cd_part, run_part = cmd.split(' && ', 1)
    parsed = shlex.split(run_part)
    _check('cd target is the given root, shell-quoted',
          cd_part == f'cd {shlex.quote(str(root))}', f'cd_part={cd_part!r}')
    _check('cwd survives shlex round-trip as exactly one argument (not split/executed)',
          parsed == [py3, 'workflow.py', '--project', cwd], f'parsed={parsed!r}')

def _test_existing_session_killed_then_relaunched() -> None:
    calls = _run_open_or_focus_monitor_with_stubs(session_exists=True, cwd='/tmp/existing-project')
    expected_name = _tmux_launcher_mod.generate_session_name('/tmp/existing-project')
    _check('existing session → kill_session called with the derived session name',
          calls['kill'] == expected_name, f'calls={calls!r}')
    _check('existing session → _launch_monitor called with the row cwd afterwards',
          calls['launch'] == '/tmp/existing-project', f'calls={calls!r}')

def _test_branch_launches_when_session_absent() -> None:
    calls = _run_open_or_focus_monitor_with_stubs(session_exists=False, cwd='/tmp/new-project')
    _check('no session → _launch_monitor called with the row cwd',
          calls['launch'] == '/tmp/new-project', f'calls={calls!r}')
    _check('no session → kill_session NOT called',
          calls['kill'] is None, f'calls={calls!r}')

def _test_resolve_python3_uses_plist_path_under_bare_environ() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        fake_bin = Path(tmp) / 'plist_bin'
        fake_bin.mkdir()
        fake_python3 = fake_bin / 'python3'
        fake_python3.write_text('#!/bin/sh\n')
        fake_python3.chmod(fake_python3.stat().st_mode | stat.S_IXUSR)
        plist = Path(tmp) / 'fixture.plist'
        plist.write_text(_FIXTURE_PLIST.format(path=str(fake_bin)), encoding='utf-8')
        resolved, stderr = _resolve_under_bare_environ(repo_root, plist)
        _check('python3 resolved under a bare PATH comes from the fixture plist PATH',
              resolved == str(fake_python3), f'resolved={resolved!r} expected={str(fake_python3)!r} stderr={stderr!r}')
        empty_plist = Path(tmp) / 'empty.plist'
        empty_plist.write_text(_FIXTURE_PLIST.format(path=''), encoding='utf-8')
        resolved_empty, stderr_empty = _resolve_under_bare_environ(repo_root, empty_plist)
        _check('an empty plist PATH does not resolve to the fixture python3',
              resolved_empty != str(fake_python3), f'resolved={resolved_empty!r} stderr={stderr_empty!r}')

def _resolve_under_bare_environ(repo_root: Path, plist: Path) -> tuple:
    r = subprocess.run(
        [sys.executable, '-c', _RESOLVE_SNIPPET, str(plist)],
        cwd=str(repo_root), env={'PATH': _BARE_PATH}, capture_output=True, text=True, timeout=10)
    return r.stdout.strip(), r.stderr.strip()

def _test_launch_monitor_uses_native_path_only() -> None:
    _check('_ghostty_version removed from system.py',
          not hasattr(_system_mod, '_ghostty_version'),
          f'hasattr={hasattr(_system_mod, "_ghostty_version")}')
    _check('_launch_monitor_ghostty_fallback removed from system.py',
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
    _check('_launch_monitor calls _launch_monitor_ghostty_native unconditionally',
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
