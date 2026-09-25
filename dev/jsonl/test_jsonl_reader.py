# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
CASES = ('partial_tail_kept_for_next_read', 'interior_corruption_raises', 'build_cache_turns_partial_tail', 'gpu_errors_read_all', 'message_content_shape')


# ORCHESTRATOR

def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == '--case':
        return run_case(sys.argv[2])
    results = collect_results()
    code = print_case_verdicts(results)
    return compute_exit_code(code, results)


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


def print_case_verdicts(results):
    for case, code, tail in results:
        print(f"{'PASS' if code == 0 else 'FAIL'} {case}" + ('' if code == 0 else f' :: {tail}'))
    return code


def compute_exit_code(code, results):
    return 0 if all(code == 0 for _, code, _ in results) else 1


def case_partial_tail_kept_for_next_read() -> None:
    from src.jsonl.jsonl_reader import read_json_records
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'a.jsonl'
        first = json.dumps({'n': 1}) + '\n'
        second = json.dumps({'n': 2}) + '\n'
        path.write_text(first + second[:5])
        records, pos = read_json_records(path, 0)
        assert records == [{'n': 1}] and pos == len(first.encode()), (records, pos)
        path.write_text(first + second)
        records, pos = read_json_records(path, pos)
        assert records == [{'n': 2}] and pos == len((first + second).encode()), (records, pos)


def case_interior_corruption_raises() -> None:
    from src.jsonl.jsonl_reader import read_json_records, JsonlCorruptError
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'a.jsonl'
        path.write_text('{"n": 1}\nnot json\n{"n": 3}\n')
        try:
            read_json_records(path, 0)
        except JsonlCorruptError as e:
            assert 'byte 9' in str(e), str(e)
            return
        raise AssertionError('no JsonlCorruptError')


def case_build_cache_turns_partial_tail() -> None:
    from src.panes.cache_turns import build_cache_turns
    user = {'type': 'user', 'userType': 'external', 'message': {'content': 'hello'}, 'timestamp': '2026-01-01T00:00:00Z'}
    usage = {'input_tokens': 5, 'cache_read_input_tokens': 10, 'cache_creation_input_tokens': 0, 'output_tokens': 3}
    assistant = {'type': 'assistant', 'requestId': 'r1', 'timestamp': '2026-01-01T00:00:01Z', 'message': {'usage': usage, 'content': []}}
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 't.jsonl'
        head = json.dumps(user) + '\n'
        line = json.dumps(assistant) + '\n'
        path.write_text(head + line[:20])
        turns, pos = build_cache_turns(path, 0, [])
        assert len(turns) == 1 and turns[0]['api_calls'] == [] and pos == len(head.encode()), (turns, pos)
        path.write_text(head + line)
        turns, pos = build_cache_turns(path, pos, turns)
        assert len(turns[0]['api_calls']) == 1, turns


def case_gpu_errors_read_all() -> None:
    from src.gpu_pane import errors
    with tempfile.TemporaryDirectory() as d:
        errors.ERRORS_FILE = Path(d) / 'errors.jsonl'
        assert errors._read_all() == []
        errors.ERRORS_FILE.write_text('{"code": "busy"}\n{"code": "bu')
        assert errors._read_all() == [{'code': 'busy'}]
        errors.ERRORS_FILE.write_text('{"code": "busy"}\nbroken\n{"code": "busy"}\n')
        try:
            errors._read_all()
        except ValueError:
            return
        raise AssertionError('no ValueError on interior corruption')


def case_message_content_shape() -> None:
    from src.jsonl.jsonl_parser import get_message_content
    block = {'type': 'tool_use', 'name': 'Bash'}
    assert get_message_content({'message': {'content': [block]}}) == [block]
    assert get_message_content({'type': 'attachment'}) == []
    assert get_message_content({'content': [block]}) == []


if __name__ == '__main__':
    sys.exit(main())
