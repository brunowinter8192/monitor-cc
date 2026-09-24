# INFRASTRUCTURE
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    '_test_equal_models_render_dim',
    '_test_mismatch_models_render_red',
    '_test_missing_answering_model_renders_nothing',
    '_test_missing_entry_renders_nothing',
    '_test_missing_forwarded_model_shows_plain',
    '_test_rate_limit_lines_still_work_with_new_shape',
    '_test_wired_into_expanded_call_lines',
]
_TITLE = 'answering_model_line_test'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'answering_model_line_test.md'

# ORCHESTRATOR


def main():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


# FUNCTIONS

def _import_target():
    from src.format.token_format import (
        _render_answering_model_line, _render_rate_limit_lines, _render_expanded_call_lines,
    )
    from src.colors import RED, DIM, SOFT_RESET
    return SimpleNamespace(
        answering_model_line=_render_answering_model_line,
        rate_limit_lines=_render_rate_limit_lines,
        expanded_call_lines=_render_expanded_call_lines,
        RED=RED, DIM=DIM, SOFT_RESET=SOFT_RESET,
    )


def _test_equal_models_render_dim() -> None:
    t = _import_target()
    render_fn = t.answering_model_line
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': 'claude-opus-4-6'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {DIM}model: claude-opus-4-6{SOFT_RESET}"], lines
    assert keys == [None]


def _test_mismatch_models_render_red() -> None:
    t = _import_target()
    render_fn = t.answering_model_line
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': 'claude-opus-4-6-fallback'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {RED}model: claude-opus-4-6-fallback{SOFT_RESET}"], lines
    assert keys == [None]


def _test_missing_answering_model_renders_nothing() -> None:
    t = _import_target()
    render_fn = t.answering_model_line
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': ''},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [] and keys == [], (
        "an empty answering_model (e.g. stream aborted before the first chunk) must render nothing"
    )


def _test_missing_entry_renders_nothing() -> None:
    t = _import_target()
    render_fn = t.answering_model_line
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-unknown'}
    lines, keys = render_fn(call, {'req-1': {'answering_model': 'x', 'proxy_forwarded_model': 'x'}})
    assert lines == [] and keys == []
    lines, keys = render_fn(call, None)
    assert lines == [] and keys == []
    call_no_rid = {}
    lines, keys = render_fn(call_no_rid, {'req-1': {'answering_model': 'x'}})
    assert lines == [] and keys == []


def _test_missing_forwarded_model_shows_plain() -> None:
    t = _import_target()
    render_fn = t.answering_model_line
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': '', 'answering_model': 'claude-opus-4-6'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {DIM}model: claude-opus-4-6{SOFT_RESET}"], (
        "with no proxy_forwarded_model to compare against, a mismatch cannot be asserted — "
        f"must render unobtrusively (DIM), not RED: {lines}"
    )


def _test_rate_limit_lines_still_work_with_new_shape() -> None:
    t = _import_target()
    render_fn = t.rate_limit_lines
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {
            'headers': {
                'anthropic-ratelimit-unified-5h-utilization': '0.5',
                'anthropic-ratelimit-unified-status': 'allowed',
            },
            'proxy_forwarded_model': 'claude-opus-4-6',
            'answering_model': 'claude-opus-4-6',
        },
    }
    lines, keys = render_fn(call, response_rid_map)
    assert any('5h:50%' in l for l in lines), (
        f"_render_rate_limit_lines must still find headers nested under entry['headers'] "
        f"after read_response_log's shape change: {lines}"
    )


def _test_wired_into_expanded_call_lines() -> None:
    t = _import_target()
    render_fn = t.expanded_call_lines
    DIM, RED, SOFT_RESET = t.DIM, t.RED, t.SOFT_RESET
    call = {'request_id': 'req-1', 'content_blocks': []}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': 'claude-opus-4-6-fallback'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert any(f"{RED}model: claude-opus-4-6-fallback{SOFT_RESET}" in l for l in lines), (
        f"the model line must reach the real per-call expanded-line render path: {lines}"
    )


if __name__ == '__main__':
    main()
