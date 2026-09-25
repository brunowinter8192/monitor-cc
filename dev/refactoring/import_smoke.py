# INFRASTRUCTURE
import os
import random
import tempfile
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_SKIP_PARTS = ('logs', 'hooks', '__pycache__')
_SKIP_MODULES = {'src.proxy_addon', 'src.menubar.menubar_main', 'src.menubar.hook_writer', 'src.menubar.hook_setup'}
_ORDER_SEEDS = (1, 2, 3, 4, 5)

# ORCHESTRATOR

def import_smoke_workflow() -> None:
    root, out_path = _parse_args()
    modules = _list_modules(root)
    jobs = _build_jobs(modules)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda job: _run_job(root, job), jobs))
    _write_report(results, out_path)
    _print_summary(results)

# FUNCTIONS

def _parse_args() -> tuple:
    return Path(sys.argv[1]).resolve(), Path(sys.argv[2])

def _list_modules(root: Path) -> list:
    modules = []
    for path in sorted((root / 'src').rglob('*.py')):
        rel = path.relative_to(root).with_suffix('')
        if any(part in _SKIP_PARTS for part in rel.parts):
            continue
        parts = list(rel.parts[:-1]) if rel.name == '__init__' else list(rel.parts)
        name = '.'.join(parts)
        if name not in _SKIP_MODULES and not name.endswith('__main__'):
            modules.append(name)
    return modules

def _build_jobs(modules: list) -> list:
    jobs = [('solo:' + m, [m]) for m in modules]
    for seed in _ORDER_SEEDS:
        order = modules[:]
        random.Random(seed).shuffle(order)
        jobs.append((f'order{seed}', order))
    return jobs

def _run_job(root: Path, job: tuple) -> tuple:
    label, order = job
    code = 'import sys, importlib\nfor m in sys.argv[1:]:\n    importlib.import_module(m)\n'
    with tempfile.TemporaryDirectory() as tmp_root:
        env = {**os.environ, 'PROXY_LOG_ID': 'import_smoke', 'PROXY_PROJECT_PATH': '', 'MONITOR_CC_ROOT': tmp_root}
        proc = subprocess.run([sys.executable, '-c', code, *order], capture_output=True, text=True, cwd=str(root), timeout=300, env=env)
    last = proc.stderr.strip().splitlines()[-1:] if proc.returncode else []
    return label, proc.returncode, last

def _write_report(results: list, out_path: Path) -> None:
    lines = [f'{label} exit={code} {" ".join(last)}' for label, code, last in sorted(results)]
    out_path.write_text('\n'.join(lines) + '\n')

def _print_summary(results: list) -> None:
    failed = [r for r in results if r[1] != 0]
    print(f'jobs={len(results)} failed={len(failed)}')

if __name__ == '__main__':
    import_smoke_workflow()
