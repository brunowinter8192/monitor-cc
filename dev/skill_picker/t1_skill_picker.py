# INFRASTRUCTURE
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.test_env import isolate_home

from dev.skill_picker.t1_discovery_cases import (
    _case_discovery_manifest_missing, _case_discovery_names, _case_discovery_plugins,
    _case_discovery_project_personal, _case_discovery_tripwires)
from dev.skill_picker.t1_insert_cases import _case_applescript, _case_insert_paths, _case_insert_text
from dev.skill_picker.t1_panel_cases import _case_controller, _case_grid, _case_isolation, _case_menu

_REPORT_DIR = Path(__file__).resolve().parent / 'md'

_CASES = {
    'discovery_plugins': _case_discovery_plugins,
    'discovery_manifest_missing': _case_discovery_manifest_missing,
    'discovery_tripwires': _case_discovery_tripwires,
    'discovery_names': _case_discovery_names,
    'discovery_project_personal': _case_discovery_project_personal,
    'insert_text': _case_insert_text,
    'applescript': _case_applescript,
    'insert_paths': _case_insert_paths,
    'menu': _case_menu,
    'grid': _case_grid,
    'controller': _case_controller,
    'isolation': _case_isolation,
}


# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    if args.case:
        _run_case_in_child(args.case)
        return
    names = sorted(_CASES)
    results = collect_results(names)
    text = _build_report(results)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = compute_path()
    path.write_text(text, encoding='utf-8')
    print(text)
    print(f'report: {path}')
    if check_condition(results):
        sys.exit(1)


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--case')
    return p.parse_args()


def _run_case_in_child(name: str) -> None:
    try:
        isolate_home()
        detail = _CASES[name]()
        print(json.dumps({'ok': True, 'detail': detail}))
    except AssertionError as exc:
        print(json.dumps({'ok': False, 'detail': f'ASSERT {exc}'}))
    except Exception as exc:
        print(json.dumps({'ok': False, 'detail': f'ERROR {exc!r}'}))


def collect_results(names):
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(_spawn_case, names))
    return results


def _spawn_case(name: str) -> dict:
    r = subprocess.run([sys.executable, '-m', 'dev.skill_picker.t1_skill_picker', '--case', name],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=120)
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines:
        return {'name': name, 'ok': False, 'detail': f'rc={r.returncode} stderr={r.stderr.strip()[-400:]}'}
    out = json.loads(lines[-1])
    out['name'] = name
    return out


def _build_report(results) -> str:
    lines = ['# t1_skill_picker report', '',
             '- every case ran in its own subprocess with an isolated HOME, all cases in parallel',
             '- nothing in this test types into a terminal or opens a menu', '',
             '| case | result | detail |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["name"]} | {"PASS" if r["ok"] else "FAIL"} | {r["detail"]} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(r["ok"] for r in results) else "FAIL"}')
    return '\n'.join(lines)


def compute_path():
    return _REPORT_DIR / f'{Path(__file__).stem}.md'


def check_condition(results):
    return any(not r['ok'] for r in results)


if __name__ == '__main__':
    main()
