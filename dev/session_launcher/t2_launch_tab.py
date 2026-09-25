# INFRASTRUCTURE
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report
from dev.session_launcher.test_env import isolate_home

from dev.session_launcher.t2_launch_cases import (
    _case_click_handling, _case_headers, _case_log_isolation, _case_occupied_marking, _case_project_rows,
    _case_request_on_open, _case_tick_and_selection)
from dev.session_launcher.t2_space_switch_cases import _case_space_switch_units
from dev.session_launcher.t2_workflow_cases import (
    _case_start_command, _case_workflow_failures, _case_workflow_success)

_CASES = {
    'log_isolation': _case_log_isolation,
    'request_on_open': _case_request_on_open,
    'headers': _case_headers,
    'occupied_marking': _case_occupied_marking,
    'tick_and_selection': _case_tick_and_selection,
    'project_rows': _case_project_rows,
    'start_command': _case_start_command,
    'workflow_success': _case_workflow_success,
    'workflow_failures': _case_workflow_failures,
    'click_handling': _case_click_handling,
    'space_switch_units': _case_space_switch_units,
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
    path = write_report(__file__, text)
    print(text)
    print_report(path)
    if any_case_failed(results):
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
    r = subprocess.run([sys.executable, '-m', 'dev.session_launcher.t2_launch_tab', '--case', name],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=120)
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines:
        return {'name': name, 'ok': False, 'detail': f'rc={r.returncode} stderr={r.stderr.strip()[-400:]}'}
    out = json.loads(lines[-1])
    out['name'] = name
    return out


def _build_report(results) -> str:
    lines = ['# t2_launch_tab report', '',
             '- every case ran in its own subprocess, all cases in parallel', '',
             '| case | result | detail |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["name"]} | {"PASS" if r["ok"] else "FAIL"} | {r["detail"]} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(r["ok"] for r in results) else "FAIL"}')
    return '\n'.join(lines)


def print_report(path):
    print(f'report: {path}')


def any_case_failed(results):
    return any(not r['ok'] for r in results)


if __name__ == '__main__':
    main()
