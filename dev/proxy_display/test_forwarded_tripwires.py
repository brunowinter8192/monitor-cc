# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
CASES = ('missing_marker_noted_once', 'short_marker_raises', 'marker_log_id_used', 'delta_without_state_raises')


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
    (root / 'src' / 'logs').mkdir(parents=True)
    return root


def case_missing_marker_noted_once() -> None:
    from src.proxy_display import forwarded_parser
    with tempfile.TemporaryDirectory() as td:
        root = make_root(td)
        notes = []
        forwarded_parser.log_pane_note = lambda name, message: notes.append((name, message))
        assert forwarded_parser._resolve_log_id(str(root), 'abcd1234') == 'abcd1234'
        assert forwarded_parser._resolve_log_id(str(root), 'abcd1234') == 'abcd1234'
        assert len(notes) == 1 and 'abcd1234' in notes[0][1], notes


def case_short_marker_raises() -> None:
    from src.proxy_display import forwarded_parser
    with tempfile.TemporaryDirectory() as td:
        root = make_root(td)
        (root / 'src' / 'logs' / '.proxy_session_abcd1234').write_text('only-one-line\n')
        try:
            forwarded_parser._resolve_log_id(str(root), 'abcd1234')
        except IndexError:
            pass
        else:
            raise AssertionError('short marker accepted')
        (root / 'src' / 'logs' / '.proxy_session_abcd1234').write_text('first\n\n')
        try:
            forwarded_parser._resolve_log_id(str(root), 'abcd1234')
        except ValueError:
            return
        raise AssertionError('empty log id accepted')


def case_marker_log_id_used() -> None:
    from src.proxy_display import forwarded_parser
    with tempfile.TemporaryDirectory() as td:
        root = make_root(td)
        (root / 'src' / 'logs' / '.proxy_session_abcd1234').write_text('first\nlogid_x\n')
        assert forwarded_parser._resolve_log_id(str(root), 'abcd1234') == 'logid_x'


def case_delta_without_state_raises() -> None:
    from src.proxy_display.forwarded_parser import _process_forwarded_entry
    fwd = {'type': 'forwarded_delta', 'flow_id': 'f9', 'model': 'claude-opus-4', 'is_first': False, 'counts': {'system': 0, 'tools': 0, 'messages': 1}, 'messages_delta': {'0': {'role': 'user', 'content': 'x'}}}
    try:
        _process_forwarded_entry(fwd, 0, {})
    except LookupError:
        return
    raise AssertionError('delta without earlier state accepted')


if __name__ == '__main__':
    sys.exit(main())
