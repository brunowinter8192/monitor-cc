# INFRASTRUCTURE
import ast
import importlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# ORCHESTRATOR


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == '--case':
        run_case(sys.argv[2])
        return
    names = collect_cases()
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(spawn_case, names))
    report(results)


# FUNCTIONS


def collect_cases() -> list:
    return sorted(n[len('case_'):] for n in globals() if n.startswith('case_'))


def run_case(name: str) -> None:
    globals()['case_' + name]()
    print('PASS')


def spawn_case(name: str) -> tuple:
    proc = subprocess.run([sys.executable, __file__, '--case', name], capture_output=True, text=True)
    return name, proc.returncode == 0, (proc.stdout + proc.stderr).strip().splitlines()[-1:]


def report(results: list) -> None:
    failed = [r for r in results if not r[1]]
    for name, ok, tail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ('' if ok else f'  {tail}'))
    print(f'{len(results) - len(failed)}/{len(results)} cases passed')
    sys.exit(1 if failed else 0)


def fresh_env(**env) -> None:
    for key in ('MONITOR_CC_ROOT', 'PROJECT_ROOT'):
        os.environ.pop(key, None)
    os.environ.update(env)


def case_env_wins() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(MONITOR_CC_ROOT=tmp)
        seen = []
        root = resolve_monitor_cc_root(lambda r, s: seen.append((r, s)))
        assert root == Path(tmp) and seen == [(Path(tmp), 'env')], (root, seen)


def case_computed_is_repo_root() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    fresh_env()
    seen = []
    root = resolve_monitor_cc_root(lambda r, s: seen.append((r, s)))
    assert root == _ROOT and seen == [(_ROOT, 'computed')], (root, seen)


def case_empty_env_counts_as_unset() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    fresh_env(MONITOR_CC_ROOT='')
    assert resolve_monitor_cc_root(lambda r, s: None) == _ROOT


def case_missing_directory_raises() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    fresh_env(MONITOR_CC_ROOT='/nonexistent/monitor_cc_root_probe')
    try:
        resolve_monitor_cc_root(lambda r, s: None)
    except FileNotFoundError as exc:
        assert 'MONITOR_CC_ROOT' in str(exc)
        return
    raise AssertionError('no raise')


def case_report_once_per_resolution() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        seen = []
        report_fn = lambda r, s: seen.append(r)
        fresh_env(MONITOR_CC_ROOT=a)
        resolve_monitor_cc_root(report_fn)
        resolve_monitor_cc_root(report_fn)
        assert seen == [Path(a)], seen
        fresh_env(MONITOR_CC_ROOT=b)
        resolve_monitor_cc_root(report_fn)
        assert seen == [Path(a), Path(b)], seen


def case_custom_env_var() -> None:
    from src.monitor_root import resolve_monitor_cc_root
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(PROJECT_ROOT=tmp, MONITOR_CC_ROOT='/nonexistent')
        assert resolve_monitor_cc_root(lambda r, s: None, 'PROJECT_ROOT') == Path(tmp)


def case_janitor_writes_root_line() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(MONITOR_CC_ROOT=tmp)
        janitor = importlib.import_module('src.monitor_janitor')
        assert janitor._resolve_monitor_cc_root() == Path(tmp)
        text = (Path(tmp) / 'src' / 'logs' / 'monitor_sweep.log').read_text()
        assert f'ROOT source=env root={tmp}' in text, text


def case_proxy_display_reports_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(MONITOR_CC_ROOT=tmp)
        parser = importlib.import_module('src.proxy_display.parser')
        forwarded = importlib.import_module('src.proxy_display.forwarded_parser')
        notes = []
        forwarded.log_pane_note = lambda pane, message: notes.append((pane, message))
        path = parser.find_errors_log_path('/probe/project')
        parser.find_response_log_path('/probe/project')
        assert str(path).startswith(str(Path(tmp) / 'src' / 'logs' / 'dual_log')), path
        assert [n for n in notes if n[0] == 'monitor_root'] == [('monitor_root', f'source=env root={tmp}')], notes
        side_logs = importlib.import_module('src.proxy_display.side_logs')
        assert side_logs._monitor_root() == Path(tmp)


def case_ram_audit_dump_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(MONITOR_CC_ROOT=tmp)
        instrument = importlib.import_module('src.ram_audit.instrument')
        notes = []
        instrument.log_pane_note = lambda pane, message: notes.append(message)
        path = instrument._resolve_dump_path('probe', '20260101_000000')
        assert path == Path(tmp) / 'dev' / 'ram_audit' / 'dumps' / '20260101_000000_probe.txt', path
        assert notes == [f'source=env root={tmp}'], notes


def case_dual_log_dir_branches() -> None:
    discovery = importlib.import_module('src.dual_log_cli.discovery')
    with tempfile.TemporaryDirectory() as tmp:
        fresh_env(MONITOR_CC_ROOT=tmp)
        err = io.StringIO()
        with redirect_stderr(err):
            found = discovery.resolve_dual_log_dir()
        assert found == Path(tmp) / 'src' / 'logs' / 'dual_log', found
        lines = err.getvalue().splitlines()
        assert lines == [f'monitor root: {tmp} (env)', f'dual_log dir: {found} (env root)'], lines
        fresh_env()
        (Path(tmp) / 'src' / 'logs' / 'dual_log').mkdir(parents=True)
        discovery.resolve_monitor_cc_root = lambda report, env_var='MONITOR_CC_ROOT': Path(tmp)
        err = io.StringIO()
        with redirect_stderr(err):
            found = discovery.resolve_dual_log_dir()
        assert found == Path(tmp) / 'src' / 'logs' / 'dual_log' and err.getvalue().strip().endswith('(repo root)'), err.getvalue()


def case_menubar_report_root() -> None:
    package = types.ModuleType('fakepkg')
    package.__path__ = []
    logged = []
    fake_log = types.ModuleType('fakepkg.menubar_log')
    fake_log.log_menubar = lambda category, message: logged.append((category, message))
    sys.modules['fakepkg'] = package
    sys.modules['fakepkg.menubar_log'] = fake_log
    spec = importlib.util.spec_from_file_location('fakepkg.root_report', _ROOT / 'src' / 'menubar' / 'root_report.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['fakepkg.root_report'] = module
    spec.loader.exec_module(module)
    module.report_root(Path('/probe'), 'env')
    assert logged == [('paths', 'PROJECT_ROOT resolved: source=env root=/probe')], logged


def case_menubar_sources_no_local_root_logic() -> None:
    for name, expected_import in (('paths.py', 'resolve_monitor_cc_root'), ('setup_menubar.py', 'MONITOR_CC_ROOT')):
        source = (_ROOT / 'src' / 'menubar' / name).read_text()
        tree = ast.parse(source)
        assert 'environ' not in source and '__file__' not in source.replace("_PLIST_TMPL      = Path(__file__)", ''), name
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
        assert expected_import in imported, (name, imported)
    assert 'resolve_monitor_cc_root(report_root, "PROJECT_ROOT")' in (_ROOT / 'src' / 'menubar' / 'paths.py').read_text()


if __name__ == '__main__':
    main()
