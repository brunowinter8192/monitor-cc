# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
CASES = ('janitor_partition_and_atomic_write', 'janitor_failure_logged', 'synthetic_user_noted_once', 'format_timestamp_states', 'rate_limit_header_states')


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


def case_janitor_partition_and_atomic_write() -> None:
    from src.panes import log_janitor
    notes = []
    log_janitor.log_pane_note = lambda name, message: notes.append((name, message))
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'x.jsonl'
        old = '{"ts": "2020-01-01T00:00:00+00:00"}\n'
        fresh = '{"ts": "2099-01-01T00:00:00+00:00"}\n'
        bad_ts = '{"ts": "2099-01-01T00:00:00+00:00Z"}\n'
        naive = '{"ts": "2020-01-01T00:00:00"}\n'
        no_ts = '{"other": 1}\n'
        path.write_text(old + fresh + bad_ts + naive + no_ts + 'not json\n')
        log_janitor.cleanup_old_jsonl(path)
        assert path.read_text() == fresh + bad_ts + naive + no_ts + 'not json\n', path.read_text()
        assert not (Path(td) / 'x.jsonl.tmp').exists()
        assert len(notes) == 1 and 'kept 3 lines' in notes[0][1], notes


def case_janitor_failure_logged() -> None:
    from src.panes import log_janitor
    errors = []
    log_janitor.log_pane_error = lambda name: errors.append(name)
    with tempfile.TemporaryDirectory() as td:
        log_janitor.cleanup_old_jsonl(Path(td))
    assert errors == ['log_janitor'], errors


def case_synthetic_user_noted_once() -> None:
    import json
    from src.panes import cache_turns
    notes = []
    cache_turns.log_pane_note = lambda name, message: notes.append(message)
    user = {'type': 'user', 'userType': 'external', 'message': {'content': 'hello'}, 'timestamp': '2026-01-01T00:00:00Z'}
    usage = {'input_tokens': 5, 'cache_read_input_tokens': 10, 'cache_creation_input_tokens': 0, 'output_tokens': 3}
    def assistant(rid, sec):
        return {'type': 'assistant', 'requestId': rid, 'timestamp': f'2026-01-01T00:00:{sec:02d}Z', 'message': {'usage': usage, 'content': []}}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 't.jsonl'
        text = json.dumps(user) + '\n' + json.dumps(assistant('r1', 1)) + '\n'
        path.write_text(text)
        turns, pos = cache_turns.build_cache_turns(path, 0, [])
        assert notes == []
        for i, rid in enumerate(('r2', 'r3')):
            text += json.dumps(assistant(rid, 2 + i)) + '\n'
            path.write_text(text)
            turns, pos = cache_turns.build_cache_turns(path, pos, turns)
        assert len(turns[0]['api_calls']) == 3, turns
        assert len(notes) == 1, notes


def case_format_timestamp_states() -> None:
    from src.utils import format_timestamp
    from src.constants import NO_TIME_PLACEHOLDER
    assert format_timestamp('') == NO_TIME_PLACEHOLDER == '--:--:--'
    assert len(format_timestamp('2026-01-01T10:00:00Z')) == 8
    try:
        format_timestamp('not a time')
    except ValueError:
        return
    raise AssertionError('malformed timestamp accepted')


def case_rate_limit_header_states() -> None:
    from src.format.token_format import _fmt_rl_reset_time, _render_rate_limit_lines
    call = {'request_id': 'r1'}
    def lines_for(headers):
        return _render_rate_limit_lines(call, {'r1': {'headers': headers}})[0]
    only_rl = lines_for({'anthropic-ratelimit-unified-5h-utilization': '0.5'})
    assert len(only_rl) == 1
    denied = lines_for({'anthropic-ratelimit-unified-status': 'denied'})
    assert len(denied) == 1 and 'status:denied' in denied[0]
    assert lines_for({'anthropic-ratelimit-unified-status': 'allowed'}) == []
    try:
        _fmt_rl_reset_time('abc')
    except ValueError:
        return
    raise AssertionError('malformed reset header accepted')


if __name__ == '__main__':
    sys.exit(main())
