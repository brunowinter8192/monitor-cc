# INFRASTRUCTURE
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.menubar import proc_cache
from case_strands import case_runners, report_case, run_case_strands

_FIXED_NOW = 1000.0


# ORCHESTRATOR

def test_bg_task_detection_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, fn = case
    ok, detail = fn()
    report_case(desc, ok, '' if ok else f'\n           {detail}')


@contextmanager
def _scratch_tasks_base():
    with tempfile.TemporaryDirectory(prefix='bg_probe_') as tmp:
        base = Path(tmp).resolve()
        with patch.object(proc_cache, '_TASKS_BASE', base), \
                patch.object(proc_cache, '_TASKS_BASE_REAL', str(base)), \
                patch.object(proc_cache, '_bg_task_open_paths', set()), \
                patch.object(proc_cache, '_bg_task_holder_pids', {}), \
                patch.object(proc_cache, '_bg_task_last_refresh', 0.0):
            yield base


def _case_match_true() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/sess1/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is True, f'want True, got {got}'


def _case_no_match_false() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/other_sess/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False, got {got}'


def _case_prefix_boundary() -> tuple:
    with _scratch_tasks_base():
        proc_cache._bg_task_open_paths = {
            f'{proc_cache._TASKS_BASE_REAL}/enc1/sess12/tasks/abc.output'
        }
        got = proc_cache._has_active_bg('enc1', 'sess1')
    return got is False, f'want False (no session-id prefix collision), got {got}'


def _case_fail_open() -> tuple:
    def _raising_run(*a, **kw):
        raise OSError('lsof unavailable (synthetic)')

    with _scratch_tasks_base(), patch.object(proc_cache, 'subprocess', SimpleNamespace(run=_raising_run)):
        proc_cache._bg_task_open_paths = {'stale/should/stay'}
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(_FIXED_NOW)
        got = proc_cache._has_active_bg('enc1', 'sess1')
        stale_kept = proc_cache._bg_task_open_paths == {'stale/should/stay'}
    return (got is False and stale_kept), f'got={got} (want False), stale_kept={stale_kept} (want True)'


def _case_ttl_gate() -> tuple:
    calls = []

    def _counting_run(*a, **kw):
        calls.append(1)
        return SimpleNamespace(stdout='', returncode=0)

    with _scratch_tasks_base(), patch.object(proc_cache, 'subprocess', SimpleNamespace(run=_counting_run)):
        proc_cache._bg_task_last_refresh = 0.0
        proc_cache._refresh_bg_task_cache(_FIXED_NOW)
        proc_cache._refresh_bg_task_cache(_FIXED_NOW + 0.1)
    return len(calls) == 1, f'lsof invocations={len(calls)} (want 1)'


CASES = [
    ('open path under session tasks dir -> True',            _case_match_true),
    ('no open path for session -> False',                     _case_no_match_false),
    ('session-id prefix collision does not false-positive',   _case_prefix_boundary),
    ('lsof failure fails open, keeps prior snapshot',         _case_fail_open),
    ('TTL gate: second call inside window is a no-op',        _case_ttl_gate),
]


if __name__ == "__main__":
    test_bg_task_detection_workflow()
