# INFRASTRUCTURE
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE = (
    "import json, runpy, sys\n"
    "ns = runpy.run_path(sys.argv[1])\n"
    "import src.proxy.addon, src.proxy.tools, src.monitor_root\n"
    "ns['addons'][0]\n"
    "print(json.dumps({'proxy': src.proxy.tools.__file__, 'root_module': src.monitor_root.__file__}))\n"
)


# ORCHESTRATOR

def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == '--case':
        run_selected_case()
        print('PASS')
        return
    names = compute_names()
    results = collect_results(names)
    report(results)


# FUNCTIONS

def run_selected_case():
    globals()['case_' + sys.argv[2]]()


def compute_names():
    return sorted(n[len('case_'):] for n in globals() if n.startswith('case_'))


def collect_results(names):
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(spawn_case, names))
    return results


def spawn_case(name: str) -> tuple:
    proc = subprocess.run([sys.executable, __file__, '--case', name], capture_output=True, text=True)
    return name, proc.returncode == 0, (proc.stdout + proc.stderr).strip().splitlines()[-1:]


def report(results: list) -> None:
    failed = [r for r in results if not r[1]]
    for name, ok, tail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ('' if ok else f'  {tail}'))
    print(f'{len(results) - len(failed)}/{len(results)} cases passed')
    sys.exit(1 if failed else 0)


def build_mirror(tmp: Path, live: bool, with_package: bool = True) -> Path:
    shutil.copytree(_ROOT / 'src', tmp / 'src', ignore=shutil.ignore_patterns('logs', '__pycache__'))
    write_mitmproxy_stub(tmp / 'stubs')
    logs = tmp / 'src' / 'logs'
    logs.mkdir()
    if not live:
        return tmp / 'src' / 'proxy_addon.py'
    shim = logs / '.proxy_addon_live_T.py'
    shutil.copy(_ROOT / 'src' / 'proxy_addon.py', shim)
    live_dir = logs / '.proxy_live_T'
    live_dir.mkdir()
    if with_package:
        (live_dir / 'src').mkdir()
        for name in ('__init__.py', 'constants.py', 'monitor_root.py'):
            shutil.copy(_ROOT / 'src' / name, live_dir / 'src' / name)
        shutil.copytree(_ROOT / 'src' / 'proxy', live_dir / 'src' / 'proxy', ignore=shutil.ignore_patterns('__pycache__'))
    return shim


def write_mitmproxy_stub(stubs: Path) -> None:
    (stubs / 'mitmproxy').mkdir(parents=True)
    (stubs / 'mitmproxy' / '__init__.py').write_text('')
    (stubs / 'mitmproxy' / 'http.py').write_text('class HTTPFlow: pass\nclass Request: pass\n')


def probe(shim: Path, env: dict, stubs: Path) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items() if k not in ('MONITOR_CC_ROOT', 'PYTHONPATH')}
    full['PROXY_LOG_ID'] = 'opus_probe_0'
    full.update(env)
    full['PYTHONPATH'] = str(stubs)
    return subprocess.run([sys.executable, '-c', _PROBE, str(shim)], capture_output=True, text=True, env=full, cwd='/')


def check_loaded(tmp: Path, out: dict, expected_proxy_parent: Path, expected_root: Path) -> None:
    assert Path(out['proxy']).parent == expected_proxy_parent, out
    assert Path(out['root_module']) == expected_proxy_parent.parent / 'monitor_root.py', out
    text = (tmp / 'src' / 'logs' / 'proxy_error.log').read_text()
    assert f'[monitor_root] source=' in text and f'root={expected_root}' in text, text


def case_live_copy_env_set() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        shim = build_mirror(tmp, live=True)
        done = probe(shim, {'MONITOR_CC_ROOT': str(tmp)}, tmp / 'stubs')
        assert done.returncode == 0, done.stderr[-300:]
        check_loaded(tmp, json.loads(done.stdout), tmp / 'src' / 'logs' / '.proxy_live_T' / 'src' / 'proxy', tmp)
        assert 'source=env' in (tmp / 'src' / 'logs' / 'proxy_error.log').read_text()


def case_non_live_layout() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        shim = build_mirror(tmp, live=False)
        done = probe(shim, {'MONITOR_CC_ROOT': str(tmp)}, tmp / 'stubs')
        assert done.returncode == 0, done.stderr[-300:]
        check_loaded(tmp, json.loads(done.stdout), tmp / 'src' / 'proxy', tmp)


def case_missing_package_raises() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        shim = build_mirror(tmp, live=True, with_package=False)
        done = probe(shim, {'MONITOR_CC_ROOT': str(tmp)}, tmp / 'stubs')
        assert done.returncode != 0 and 'FileNotFoundError: proxy package not found' in done.stderr, done.stderr[-300:]


def case_missing_root_directory_raises() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        shim = build_mirror(tmp, live=True)
        done = probe(shim, {'MONITOR_CC_ROOT': str(tmp / 'absent')}, tmp / 'stubs')
        assert done.returncode != 0 and 'MONITOR_CC_ROOT resolved via env to a missing directory' in done.stderr, done.stderr[-300:]


if __name__ == '__main__':
    main()
