# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = os.environ.get('MCFIX_TREE') or str(REPO_ROOT)
CASES = ('render_expanded_without_messages', 'lazy_load_unmatched_raises', 'toggle_failure_keeps_state', 'reparse_clears_expand_states')


# ORCHESTRATOR

def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == '--case':
        return run_case(sys.argv[2])
    with ThreadPoolExecutor(max_workers=len(CASES)) as pool:
        results = list(pool.map(run_strand, CASES))
    for case, code, tail in results:
        print(f"{'PASS' if code == 0 else 'FAIL'} {case}" + ('' if code == 0 else f' :: {tail}'))
    return 0 if all(code == 0 for _, code, _ in results) else 1


# FUNCTIONS

def run_case(case: str) -> int:
    sys.path.insert(0, TREE)
    globals()['case_' + case]()
    return 0


def run_strand(case: str) -> tuple:
    proc = subprocess.run([sys.executable, __file__, '--case', case], capture_output=True, text=True, env={**os.environ, 'MCFIX_TREE': TREE})
    tail = (proc.stderr.strip().splitlines() or [''])[-1]
    return case, proc.returncode, tail


def fwd_line(flow_id: str, is_first: bool = True) -> dict:
    return {'type': 'forwarded_delta', 'flow_id': flow_id, 'model': 'claude-opus-4', 'is_first': is_first, 'counts': {'system': 0, 'tools': 0, 'messages': 1}, 'messages_delta': {'0': {'role': 'user', 'content': 'hi'}}, 'timestamp': '2026-01-01T00:00:00Z'}


def bare_entry(flow_id: str = 'f1') -> dict:
    from src.proxy_display.forwarded_parser import _extract_forwarded_fields
    entry = _extract_forwarded_fields(fwd_line(flow_id), [], [], [], [])
    entry['flow_id'] = flow_id
    entry['diff_from_prev'] = None
    return entry


def case_render_expanded_without_messages() -> None:
    from src.proxy_display.format import format_proxy_block
    from src.proxy_display.proxy_pane_shared import _attach_overlay_references
    from src.proxy_display.forwarded_parser import _infer_model_family
    from src.proxy_display.turn_cache import TurnCache
    entry = bare_entry()
    _attach_overlay_references([entry], {}, {}, _infer_model_family)
    body, total = format_proxy_block([entry], {('req', 0): True}, {}, None, 50, 100, 0, turn_cache=TurnCache('t'))
    assert total > 0


def case_lazy_load_unmatched_raises() -> None:
    from src.proxy_display.forwarded_parser import _lazy_load_messages_forwarded
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'x_forwarded.jsonl'
        path.write_text(json.dumps(fwd_line('other')) + '\n')
        entry = bare_entry('missing')
        try:
            _lazy_load_messages_forwarded(entry, path)
        except LookupError:
            assert 'messages' not in entry
            return
        raise AssertionError('no LookupError')


def case_toggle_failure_keeps_state() -> None:
    from src.proxy_display.proxy_pane_shared import _toggle_expand_and_lazy_load
    with tempfile.TemporaryDirectory() as d:
        log_path = Path(d) / 'x.jsonl'
        (Path(d) / 'dual_log').mkdir()
        (Path(d) / 'dual_log' / 'x_forwarded.jsonl').write_text(json.dumps(fwd_line('other')) + '\n')
        states = {}
        try:
            _toggle_expand_and_lazy_load(('req', 0), 0, [bare_entry('missing')], log_path, states)
        except LookupError:
            assert states == {}
            return
        raise AssertionError('no LookupError')


def case_reparse_clears_expand_states() -> None:
    from src.proxy_display import pane, worker_proxy_pane
    pane.proxy_expand_states[('req', 3)] = True
    pane._proxy_undo_stack.append((('req', 3), False))
    pane._reset_proxy_reparse_state(1.0)
    assert pane.proxy_expand_states == {} and pane._proxy_undo_stack == []
    worker_proxy_pane.worker_proxy_expand_states[('req', 3)] = True
    worker_proxy_pane._reset_worker_proxy_reparse_state(1.0)
    assert worker_proxy_pane.worker_proxy_expand_states == {}


if __name__ == '__main__':
    sys.exit(main())
