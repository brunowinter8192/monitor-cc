"""
Unit-level regression guard for the M2 answering-model-in-token-pane milestone
(process-docs/proxy_instrumentation/).

Covers src/format/token_format.py's new _render_answering_model_line and the updated
_render_rate_limit_lines (both now read a full `_response` dual-log entry per request_id, not a
flat headers dict — src/proxy_display/side_logs.py's read_response_log changed shape to match).

Run: ./venv/bin/python dev/panes/answering_model_line_test.py
"""

# INFRASTRUCTURE
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# ORCHESTRATOR


def main():
    (_render_answering_model_line, _render_rate_limit_lines, _render_expanded_call_lines,
     RED, DIM, SOFT_RESET) = _import_target()
    _test_equal_models_render_dim(_render_answering_model_line, DIM, SOFT_RESET)
    _test_mismatch_models_render_red(_render_answering_model_line, RED, SOFT_RESET)
    _test_missing_answering_model_renders_nothing(_render_answering_model_line)
    _test_missing_entry_renders_nothing(_render_answering_model_line)
    _test_missing_forwarded_model_shows_plain(_render_answering_model_line, DIM, SOFT_RESET)
    _test_rate_limit_lines_still_work_with_new_shape(_render_rate_limit_lines)
    _test_wired_into_expanded_call_lines(_render_expanded_call_lines, RED, SOFT_RESET)
    print("[answering_model_line_test] all checks passed")


# FUNCTIONS

# Imported via a function (not a module-level `from src.` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
def _import_target():
    from src.format.token_format import (
        _render_answering_model_line, _render_rate_limit_lines, _render_expanded_call_lines,
    )
    from src.colors import RED, DIM, SOFT_RESET
    return _render_answering_model_line, _render_rate_limit_lines, _render_expanded_call_lines, RED, DIM, SOFT_RESET


def _test_equal_models_render_dim(render_fn, DIM, SOFT_RESET) -> None:
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': 'claude-opus-4-6'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {DIM}model: claude-opus-4-6{SOFT_RESET}"], lines
    assert keys == [None]


def _test_mismatch_models_render_red(render_fn, RED, SOFT_RESET) -> None:
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': 'claude-opus-4-6-fallback'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {RED}model: claude-opus-4-6-fallback{SOFT_RESET}"], lines
    assert keys == [None]


def _test_missing_answering_model_renders_nothing(render_fn) -> None:
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': 'claude-opus-4-6', 'answering_model': ''},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [] and keys == [], (
        "an empty answering_model (e.g. stream aborted before the first chunk) must render nothing"
    )


def _test_missing_entry_renders_nothing(render_fn) -> None:
    call = {'request_id': 'req-unknown'}
    lines, keys = render_fn(call, {'req-1': {'answering_model': 'x', 'proxy_forwarded_model': 'x'}})
    assert lines == [] and keys == []
    lines, keys = render_fn(call, None)
    assert lines == [] and keys == []
    call_no_rid = {}
    lines, keys = render_fn(call_no_rid, {'req-1': {'answering_model': 'x'}})
    assert lines == [] and keys == []


def _test_missing_forwarded_model_shows_plain(render_fn, DIM, SOFT_RESET) -> None:
    call = {'request_id': 'req-1'}
    response_rid_map = {
        'req-1': {'proxy_forwarded_model': '', 'answering_model': 'claude-opus-4-6'},
    }
    lines, keys = render_fn(call, response_rid_map)
    assert lines == [f"    {DIM}model: claude-opus-4-6{SOFT_RESET}"], (
        "with no proxy_forwarded_model to compare against, a mismatch cannot be asserted — "
        f"must render unobtrusively (DIM), not RED: {lines}"
    )


def _test_rate_limit_lines_still_work_with_new_shape(render_fn) -> None:
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


def _test_wired_into_expanded_call_lines(render_fn, RED, SOFT_RESET) -> None:
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
