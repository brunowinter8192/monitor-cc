# INFRASTRUCTURE
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AREA_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = AREA_DIR.parents[1]
DRIVER = AREA_DIR / 'm2_state_sequence_driver.py'
REPORT_DIR = AREA_DIR / 'md'
OLD_REF = '0ce370df'
FIXTURES = AREA_DIR / 'fixtures'
SESSIONS = {
    'many_calls': FIXTURES / 'many_calls.jsonl',
    'many_turns': FIXTURES / 'many_turns.jsonl',
}
PANES = ['tokens', 'worker_tokens']

# ORCHESTRATOR

def test_workflow() -> int:
    with tempfile.TemporaryDirectory(prefix='flicker_m2_') as tmp:
        work_dir = Path(tmp)
        old_root = extract_old_tree(work_dir)
        outputs = run_all_drivers(old_root, work_dir)
    verdicts = evaluate(outputs)
    write_report(verdicts, old_root)
    return 0 if all(ok for _, ok, _ in verdicts) else 1

# FUNCTIONS

def extract_old_tree(work_dir: Path) -> Path:
    old_root = work_dir / 'old_tree'
    old_root.mkdir()
    archive = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'archive', OLD_REF], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(old_root)], input=archive, check=True)
    return old_root

def run_all_drivers(old_root: Path, work_dir: Path) -> dict:
    jobs = [(pane, session, tree) for pane in PANES for session in SESSIONS for tree in ('old', 'new')]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {j: pool.submit(run_driver, j, old_root, work_dir) for j in jobs}
        return {j: f.result() for j, f in futures.items()}

def run_driver(job: tuple, old_root: Path, work_dir: Path):
    pane, session, tree = job
    root = old_root if tree == 'old' else WORKTREE_ROOT
    out_path = work_dir / f'{pane}_{session}_{tree}.json'
    proc = subprocess.run([sys.executable, str(DRIVER), str(root), pane, str(SESSIONS[session]), str(out_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        return {'error': proc.stderr[-800:]}
    return json.loads(out_path.read_text(encoding='utf-8'))

def evaluate(outputs: dict) -> list:
    verdicts = []
    for pane in PANES:
        for session in SESSIONS:
            old, new = outputs[(pane, session, 'old')], outputs[(pane, session, 'new')]
            if isinstance(old, dict) or isinstance(new, dict):
                verdicts.append((f'{pane}/{session}: drivers ran', False, str(old if isinstance(old, dict) else new)))
                continue
            verdicts.extend(compare_runs(pane, session, old, new))
    return verdicts

def compare_runs(pane: str, session: str, old: list, new: list) -> list:
    verdicts = [(f'{pane}/{session}: same step count ({len(old)})', len(old) == len(new), '')]
    for a, b in zip(old, new):
        label = f"{pane}/{session}: step {a['name']}"
        for field in ('output', 'exc', 'line_map', 'copy_rows', 'nav', 'scroll', 'width'):
            verdicts.append((f'{label} {field} identical', a[field] == b[field], ''))
        if a['name'].startswith('hover_'):
            verdicts.append((f'{label} recomputed 0 turns (old {a["turn_renders"]})', b['turn_renders'] == 0, f'new={b["turn_renders"]}'))
    return verdicts

def write_report(verdicts: list, old_root: Path) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    ref = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'rev-parse', '--short', OLD_REF], capture_output=True, text=True).stdout.strip()
    passed = sum(1 for _, ok, _ in verdicts if ok)
    lines = ['# m2_byte_identity_test report', '',
             f'Old: git archive {OLD_REF} ({ref}); new: working tree',
             'Sessions: ' + ', '.join(f'{k}={v.name}' for k, v in SESSIONS.items()), '',
             f'Result: {passed}/{len(verdicts)} checks passed', '']
    for label, ok, hint in verdicts:
        if not ok:
            lines.append(f'- FAIL  {label}  {hint}')
    lines.append('')
    lines.append('All non-listed checks passed.' if passed == len(verdicts) else 'See FAIL lines above.')
    (REPORT_DIR / 'm2_byte_identity_test.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for label, ok, hint in verdicts:
        if not ok:
            print(f'FAIL {label} {hint}'[:300])
    print(f'{passed}/{len(verdicts)} checks passed')

if __name__ == '__main__':
    sys.exit(test_workflow())
