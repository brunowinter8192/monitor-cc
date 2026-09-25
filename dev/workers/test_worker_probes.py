# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
_PROJECT_KEY = f'/tmp/mcfix_workers_{uuid.uuid4().hex[:8]}'
CASES = ('selection_write_failure_logged', 'selection_read_only_missing_file', 'worker_status_probes', 'list_workers_has_no_model')


# ORCHESTRATOR

def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == '--case':
        return compute_result()
    results = collect_results()
    print_results(results)
    return compute_exit_code(results)


# FUNCTIONS

def compute_result():
    return run_case(sys.argv[2])


def run_case(case: str) -> int:
    sys.path.insert(0, TREE)
    globals()['case_' + case]()
    return 0


def collect_results():
    with ThreadPoolExecutor(max_workers=len(CASES)) as pool:
        results = list(pool.map(run_strand, CASES))
    return results


def run_strand(case: str) -> tuple:
    proc = subprocess.run([sys.executable, __file__, '--case', case], capture_output=True, text=True, env={**os.environ, 'MCFIX_TREE': TREE})
    tail = (proc.stderr.strip().splitlines() or [''])[-1]
    return case, proc.returncode, tail


def print_results(results):
    for case, code, tail in results:
        print(f"{'PASS' if code == 0 else 'FAIL'} {case}" + ('' if code == 0 else f' :: {tail}'))


def compute_exit_code(results):
    return 0 if all(code == 0 for _, code, _ in results) else 1


def case_selection_write_failure_logged() -> None:
    from src.workers import worker_selection
    errors = []
    worker_selection.log_pane_error = lambda name: errors.append(name)
    worker_selection.get_selection_file_path = lambda project_filter: '/nonexistent_dir_mcfix/x.txt'
    worker_selection._write_selection(f'{_PROJECT_KEY}/p', 'w1')
    assert errors == ['worker_selection'], errors


def case_selection_read_only_missing_file() -> None:
    from src.workers import worker_tokens_pane
    from src.proxy_display import worker_proxy_pane

    class FakeMonitor:
        active_project_filter = f'{_PROJECT_KEY}/p'
    with tempfile.TemporaryDirectory() as td:
        for module in (worker_tokens_pane, worker_proxy_pane):
            module.get_selection_file_path = lambda project_filter, base=td: str(Path(base) / 'missing.txt')
            assert module._read_selected_worker_name(FakeMonitor()) is None
            module.get_selection_file_path = lambda project_filter, base=td: base
            try:
                module._read_selected_worker_name(FakeMonitor())
            except OSError:
                continue
            raise AssertionError('non-ENOENT read error swallowed')


def make_fake_run(pane_dead: str, activity_rc: int, activity_out: str):
    def fake_run(cmd, capture_output=True, text=True):
        joined = ' '.join(cmd)
        if 'pane_dead' in joined:
            return subprocess.CompletedProcess(cmd, 0, pane_dead + '\n', '')
        if 'window_activity' in joined:
            return subprocess.CompletedProcess(cmd, activity_rc, activity_out, '')
        raise AssertionError(joined)
    return fake_run


def case_worker_status_probes() -> None:
    from src.workers import worker_tmux
    now = int(time.time())
    worker_tmux.subprocess.run = make_fake_run('0', 1, '')
    assert worker_tmux.detect_worker_status('s') == 'unknown'
    worker_tmux.subprocess.run = make_fake_run('0', 0, '')
    assert worker_tmux.detect_worker_status('s') == 'unknown'
    worker_tmux.subprocess.run = make_fake_run('0', 0, f'{now}\n')
    assert worker_tmux.detect_worker_status('s') == 'working'
    worker_tmux.subprocess.run = make_fake_run('0', 0, f'{now - 100}\n')
    assert worker_tmux.detect_worker_status('s') == 'idle'
    worker_tmux.subprocess.run = make_fake_run('1', 0, '')
    assert worker_tmux.detect_worker_status('s') == 'exited'


def case_list_workers_has_no_model() -> None:
    from src.workers import worker_tmux
    def fake_run(cmd, capture_output=True, text=True):
        joined = ' '.join(cmd)
        if 'list-sessions' in joined:
            return subprocess.CompletedProcess(cmd, 0, 'worker-proj-w1\n', '')
        if 'show-environment' in joined:
            return subprocess.CompletedProcess(cmd, 1, '', '')
        if 'pane_dead' in joined:
            return subprocess.CompletedProcess(cmd, 0, '1\n', '')
        raise AssertionError(joined)
    worker_tmux.subprocess.run = fake_run
    workers = worker_tmux.list_workers(f'{_PROJECT_KEY}/proj')
    assert len(workers) == 1 and 'model' not in workers[0], workers


if __name__ == '__main__':
    sys.exit(main())
