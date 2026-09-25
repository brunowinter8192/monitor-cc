# INFRASTRUCTURE
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_OLD_ROOT = Path('/tmp/pf_old')
_REPORT = _HERE / 'md' / 'run_scenarios.md'
_SCENARIOS = ('hover', 'grow_and_new_turn', 'late_response', 'late_overlay', 'expand_collapse', 'search', 'width', 'copy_feedback', 'reparse', 'unsorted_turns')
_MAX_GROUPS_ON_GROW = 2


# ORCHESTRATOR

def main():
    out_dir = Path(tempfile.mkdtemp(prefix='pf_scen_'))
    jobs = compute_jobs()
    jobs.append(('tripwire', 'new', _ROOT))
    procs = collect_procs(jobs, out_dir)
    failures = compute_failures(procs)
    results = compute_results(out_dir)
    _write_report(results, failures)
    ok = compute_ok(failures, results)
    print_result(ok)
    exit_with_status(ok)


# FUNCTIONS

def compute_jobs():
    return [(name, side, root) for name in _SCENARIOS for side, root in (('old', _OLD_ROOT), ('new', _ROOT))]


def collect_procs(jobs, out_dir):
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        procs = list(pool.map(lambda j: _run_job(j, out_dir), jobs))
    return procs


def _run_job(job: tuple, out_dir: Path) -> tuple:
    name, side, root = job
    out = out_dir / f'{side}_{name}.json'
    cmd = [str(_ROOT / 'venv' / 'bin' / 'python'), str(_HERE / 'scenario_run.py'), '--root', str(root), '--scenario', name, '--out', str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f'{side} {name} FAILED\n{proc.stderr[-2000:]}')
    return (name, side, out, proc.returncode)


def compute_failures(procs):
    return [p for p in procs if p[3] != 0]


def compute_results(out_dir):
    return [_evaluate(name, out_dir) for name in (*_SCENARIOS, 'tripwire')]


def _evaluate(name: str, out_dir: Path) -> dict:
    new = _load(out_dir / f'new_{name}.json')
    if name == 'tripwire':
        bad = [s for s in new if s[2] != 'ValueError']
        return {'name': name, 'steps': len(new), 'ok': bool(new) and not bad, 'notes': [f'tripwire outcomes: {[s[2] for s in new]}']}
    old = _load(out_dir / f'old_{name}.json')
    mismatches = [n[0] for n, o in zip(new, old) if n[2] != o[2]]
    hover_calls = sum(s[3] for s in new if s[1] == 'hover')
    grow_max = max([s[3] for s in new if s[1] == 'grow'] or [0])
    change_calls = [(s[0], s[3]) for s in new if s[1] == 'change']
    ok = bool(new) and len(new) == len(old) and not mismatches and hover_calls == 0 and grow_max <= _MAX_GROUPS_ON_GROW
    notes = [f'hover-step group renders: {hover_calls}', f'max group renders on a grow step: {grow_max}', f'change steps (label, groups rendered): {change_calls}']
    warm = [s[3] for s in new if s[1] == 'warm']
    notes.append(f'warm groups rendered: {warm}')
    return {'name': name, 'steps': len(new), 'ok': ok, 'mismatches': mismatches, 'notes': notes}


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def _write_report(results: list, failures: list) -> None:
    lines = ['# run_scenarios', '', 'Old tree: git archive of the pre-M3 commit at /tmp/pf_old. New tree: this worktree.', '', 'scenario | steps | verdict', '---|---|---']
    for r in results:
        lines.append(f"{r['name']} | {r['steps']} | {'PASS' if r['ok'] else 'FAIL'}")
    lines.append('')
    for r in results:
        lines.append(f"## {r['name']}")
        lines.append(f"- byte-identical mismatching steps: {r.get('mismatches', 'n/a')}")
        lines += [f'- {n}' for n in r['notes']]
        lines.append('')
    lines.append(f'subprocess failures: {[(f[0], f[1]) for f in failures]}')
    _REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def compute_ok(failures, results):
    return not failures and all(r['ok'] for r in results)


def print_result(ok):
    print('RESULT:', 'PASS' if ok else 'FAIL')


def exit_with_status(ok):
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
