# INFRASTRUCTURE
import re
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dev.refactoring.strand_runner import strand_workflow

_NAME_MAX_CHARS = 60
_EXTRA_INDEX = 99

# FUNCTIONS


def run_case_strands(script_globals: dict, script_path: str, runners: dict) -> int:
    script_globals.update(runners)
    return strand_workflow(script_globals, script_path, sorted(runners))


def exit_code_runners(cases: list, run_hook_fn) -> dict:
    return {strand_name(index, case[0]): partial(_check_exit_code, run_hook_fn, case) for index, case in enumerate(cases)}


def case_runners(cases: list, check_fn) -> dict:
    return {strand_name(index, case[0]): partial(check_fn, case) for index, case in enumerate(cases)}


def function_runners(functions: list) -> dict:
    return {function.__name__.lstrip('_'): function for function in functions}


def error_string_runners(functions: list) -> dict:
    return {function.__name__: partial(_check_error_string, function) for function in functions}


def strand_name(index: int, desc: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '_', desc).strip('_')[:_NAME_MAX_CHARS]
    return f'case_{index:02d}_{slug}'


def report_case(desc: str, ok: bool, detail: str = '') -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {desc}{detail}")
    if not ok:
        raise AssertionError(desc)


def _check_exit_code(run_hook_fn, case: tuple) -> None:
    desc, command, expected = case[0], case[1], case[2]
    got = run_hook_fn(command, *case[3:])
    report_case(desc, got == expected, f': exit={got} (expected {expected})')


def fail_open_runner(desc: str, run_raw_fn, payload: bytes) -> dict:
    return {strand_name(_EXTRA_INDEX, desc): partial(_check_fail_open, run_raw_fn, desc, payload)}


def _check_fail_open(run_raw_fn, desc: str, payload: bytes) -> None:
    got = run_raw_fn(payload)
    report_case(desc, got == 0, f': exit={got} (expected 0)')


def _check_error_string(function) -> None:
    error = function()
    report_case(function.__name__, error is None, '' if error is None else f': {error}')
