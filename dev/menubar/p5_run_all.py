# INFRASTRUCTURE
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_STRANDS = ['p5_g1_log.py', 'p5_g2_state.py', 'p5_g3_app.py', 'p5_g4_detection.py',
            'p5_g5_discover.py', 'p5_g6_caches.py', 'p5_g7_model.py', 'p5_g8_system.py']


# ORCHESTRATOR

def main() -> None:
    results = collect_results()
    report(results)


# FUNCTIONS

def collect_results():
    with ThreadPoolExecutor(max_workers=len(_STRANDS)) as pool:
        results = list(pool.map(run_strand, _STRANDS))
    return results


def run_strand(name: str) -> tuple:
    proc = subprocess.run([sys.executable, str(_HERE / name)], capture_output=True, text=True, timeout=300)
    return name, proc.returncode, proc.stdout, proc.stderr


def report(results: list) -> None:
    failed = []
    for name, code, out, err in results:
        checks = [l for l in out.splitlines() if l.endswith('PASS') or ': FAIL' in l]
        passed = sum(1 for l in checks if l.endswith('PASS'))
        print(f'{name}: exit={code} checks_passed={passed}')
        if code != 0:
            failed.append(name)
            print('  aborted at:', [l for l in checks if ': FAIL' in l] or err.strip()[-200:])
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
