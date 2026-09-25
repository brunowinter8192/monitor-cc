# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
CASES = ('marker_absent_is_none', 'scan_scope_and_logging', 'proxy_pane_no_session_start', 'warnings_refresh_without_marker')


# ORCHESTRATOR

def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == '--case':
        return run_case(sys.argv[2])
    results = collect_results()
    print_results(results)
    return compute_exit_code(results)


# FUNCTIONS

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


def make_root(td: str) -> Path:
    root = Path(td)
    (root / 'src' / 'logs' / 'dual_log').mkdir(parents=True)
    os.environ['MONITOR_CC_ROOT'] = str(root)
    return root


def case_marker_absent_is_none() -> None:
    from src.proxy_display.parser import get_proxy_session_start_ts
    from src.proxy_display.forwarded_parser import _proxy_session_id_for_project
    with tempfile.TemporaryDirectory() as td:
        root = make_root(td)
        assert get_proxy_session_start_ts('/tmp/some/project') is None
        marker = root / 'src' / 'logs' / f".proxy_session_{_proxy_session_id_for_project('/tmp/some/project')}"
        marker.write_text('logid\n123\n')
        assert get_proxy_session_start_ts('/tmp/some/project') == marker.stat().st_mtime


def case_scan_scope_and_logging() -> None:
    from src.proxy_display import side_logs
    with tempfile.TemporaryDirectory() as td:
        root = make_root(td)
        dual = root / 'src' / 'logs' / 'dual_log'
        (dual / 'api_requests_worker_aaaa1111_w1_1_errors.jsonl').write_text('{"a": 1}\n')
        (dual / 'api_requests_worker_bbbb2222_w2_1_errors.jsonl').write_text('{"b": 1}\n')
        (dual / 'api_requests_worker_aaaa1111_gone_1_errors.jsonl').symlink_to(dual / 'nowhere')
        logged = []
        side_logs.log_pane_error = lambda name: logged.append(name)
        records, positions = side_logs.scan_worker_errors_logs({}, 'aaaa1111', 0.0)
        assert [r['_worker_name_from_file'] for r in records] == ['w1'], records
        assert logged == ['side_logs'], logged
        try:
            side_logs.scan_worker_errors_logs({})
        except TypeError:
            return
        raise AssertionError('project scope and min_mtime are optional')


def case_proxy_pane_no_session_start() -> None:
    from src.proxy_display import pane

    class FakeMonitor:
        active_project_filter = '/tmp/x'
        def _get_newest_main_session(self):
            return None
        def _get_session_start_ts(self):
            return None
    changed, ts = pane._refresh_proxy_data(100.0, False, 0.0, FakeMonitor())
    assert changed is True and pane.proxy_entries == []
    pane._terminal_size = lambda: (30, 100)
    assert 'Session start unknown' in pane._build_proxy_output()


def case_warnings_refresh_without_marker() -> None:
    from src.panes import warnings_pane
    from src.proxy_display import side_logs
    from src.core import monitor
    with tempfile.TemporaryDirectory() as td:
        make_root(td)
        monitor.active_project_filter = '/tmp/some/project'
        def boom(*args, **kwargs):
            raise AssertionError('worker scan ran without a session marker')
        side_logs.scan_worker_errors_logs = boom
        warnings_pane._refresh_warnings_data(100.0, False, 0.0)
        assert warnings_pane._monitor_start_ts is None
        assert 'no proxy session marker' in warnings_pane._worker_errors_notice()
        from src.panes.warnings_render import _format_warnings_header
        assert 'no proxy session marker' in _format_warnings_header(1.0, 120, {}, warnings_pane._worker_errors_notice())


if __name__ == '__main__':
    sys.exit(main())
