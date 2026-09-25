# INFRASTRUCTURE
import ast
import io
import shutil
import subprocess
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

_SETUP = Path(__file__).resolve().parents[2] / 'setup_py2app.py'
_WANTED = ('_prune_bundle_bloat', '_find_signing_identity', '_install_bundle')


# ORCHESTRATOR

def main():
    results = compute_results()
    print_results(results)
    failed = compute_failed(results)
    print_passed(results, failed)
    exit_with_status(failed)


# FUNCTIONS

def compute_results():
    return _prune_checks() + _install_checks()


def _prune_checks() -> list:
    ns = _load_functions(lambda *a, **k: None)
    cwd = Path.cwd()
    tmp = Path(tempfile.mkdtemp())
    try:
        import os
        os.chdir(tmp)
        code, out = _exit_code(ns['_prune_bundle_bloat'])
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    return [('missing bundle src lib exits 1 with a message', code == 1 and 'bundle src lib missing' in out)]


def _load_functions(fake_run) -> dict:
    tree = ast.parse(_SETUP.read_text())
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in _WANTED]
    keep += [n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in ('_PYTHON_VER', '_BUNDLE_SRC_KEEP') for t in n.targets)]
    module = ast.Module(body=keep, type_ignores=[])
    fake_subprocess = types.SimpleNamespace(run=fake_run)
    ns = {'os': __import__('os'), 'shutil': shutil, 'subprocess': fake_subprocess,
          'sys': sys, 'time': types.SimpleNamespace(sleep=lambda s: None), 'Path': Path}
    ns['__file__'] = str(_SETUP)
    exec(compile(module, str(_SETUP), 'exec'), ns)
    return ns


def _exit_code(fn) -> tuple:
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            fn()
    except SystemExit as exc:
        return exc.code, out.getvalue()
    return None, out.getvalue()


def _install_checks() -> list:
    return [
        ('codesign rc!=0 exits 1', _run_install(codesign_rc=1, bootstrap_rc=0)[0] == 1),
        ('bootstrap failing twice exits 1', _run_install(codesign_rc=0, bootstrap_rc=1)[0] == 1),
        ('bootstrap retry that succeeds does not exit', _run_install(codesign_rc=0, bootstrap_rc=1, succeed_on_retry=True)[0] is None),
        ('all ok does not exit', _run_install(codesign_rc=0, bootstrap_rc=0)[0] is None),
    ]


def _run_install(codesign_rc: int, bootstrap_rc: int, succeed_on_retry: bool = False) -> tuple:
    calls = {'bootstrap': 0}

    def fake_run(argv, **kwargs):
        rc = 0
        if argv[0] == 'security':
            return types.SimpleNamespace(returncode=0, stdout=b'monitor-cc Code Signing', stderr=b'')
        if argv[0] == 'codesign':
            rc = codesign_rc
        if argv[:2] == ['launchctl', 'bootstrap']:
            calls['bootstrap'] += 1
            rc = 0 if (succeed_on_retry and calls['bootstrap'] > 1) else bootstrap_rc
        return types.SimpleNamespace(returncode=rc, stdout=b'', stderr=b'fake')

    home = Path(tempfile.mkdtemp())
    ns = _load_functions(fake_run)
    cwd = Path.cwd()
    import os
    try:
        (home / 'proj' / 'dist' / 'monitor-cc-menubar.app').mkdir(parents=True)
        (home / 'proj' / 'src' / 'menubar').mkdir(parents=True)
        (home / 'proj' / 'src' / 'menubar' / 'com.brunowinter.monitor-cc-menubar.plist').write_text('<PROJECT_ROOT><BUNDLE_LAUNCHER>')
        os.chdir(home / 'proj')
        ns['Path'] = _PathProxy(home)
        return _exit_code(ns['_install_bundle'])
    finally:
        os.chdir(cwd)
        shutil.rmtree(home, ignore_errors=True)


class _PathProxy:
    def __init__(self, home: Path):
        self._home = home

    def __call__(self, *args):
        return Path(*args)

    def home(self) -> Path:
        return self._home


def print_results(results):
    for name, ok in results:
        print(('PASS: ' if ok else 'FAIL: ') + name)


def compute_failed(results):
    return [n for n, ok in results if not ok]


def print_passed(results, failed):
    print(f'{len(results) - len(failed)}/{len(results)} passed')


def exit_with_status(failed):
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
