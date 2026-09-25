# INFRASTRUCTURE
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LIVE_LOG_DIR = '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log'
_HARNESSES = [
    'dev/proxy/pipeline_byte_identity.py',
    'dev/proxy/addon_hook_byte_identity.py',
    'dev/panes/render_byte_identity.py',
    'dev/proxy_display/render_byte_identity.py',
    'dev/gpu_pane/render_byte_identity.py',
    'dev/menubar/discover_byte_identity.py',
    'dev/menubar/model_controller_byte_identity.py',
    'dev/menubar/panel_manager_byte_identity.py',
    'dev/constants/split_byte_identity.py',
    'dev/workers/test_worker_probes.py',
    'dev/pane_flicker/m2_byte_identity_test.py',
]
_RUNNER_CODE = (
    "import sys\n"
    "path, live, snap = sys.argv[1], sys.argv[2], sys.argv[3]\n"
    "src = open(path).read().replace(live, snap)\n"
    "sys.argv = [path]\n"
    "exec(compile(src, path, 'exec'), {'__file__': path, '__name__': '__main__'})\n"
)

# ORCHESTRATOR

def pinned_harness_workflow() -> None:
    snapshot_dir, out_dir = _parse_args()
    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=len(_HARNESSES)) as pool:
        results = list(pool.map(lambda h: _run_harness(h, snapshot_dir), _HARNESSES))
    _write_results(results, out_dir)
    _print_summary(results)

# FUNCTIONS

def _parse_args() -> tuple:
    return Path(sys.argv[1]), Path(sys.argv[2])

def _run_harness(harness: str, snapshot_dir: Path) -> tuple:
    proc = subprocess.run(
        [sys.executable, '-c', _RUNNER_CODE, str(_ROOT / harness), _LIVE_LOG_DIR, str(snapshot_dir)],
        capture_output=True, text=True, timeout=600, cwd=str(_ROOT),
    )
    return harness, proc.returncode, proc.stdout, proc.stderr

def _write_results(results: list, out_dir: Path) -> None:
    for harness, code, out, err in results:
        name = harness.replace('/', '__')
        (out_dir / f'{name}.out').write_text(f'exit={code}\n{out}\n--stderr--\n{err}')

def _print_summary(results: list) -> None:
    for harness, code, out, err in results:
        hashes = [l for l in out.splitlines() if 'HASH' in l or 'PASS' in l or 'FAIL' in l][-1:]
        print(f'{harness}: exit={code} {hashes}')

if __name__ == '__main__':
    pinned_harness_workflow()
