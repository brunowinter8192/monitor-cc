# INFRASTRUCTURE
import inspect
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
os.environ.setdefault('PROXY_LOG_ID', 'opus_probe_0')

from src.proxy.addon import _write_response_and_mismatch, _write_model_mismatch_entry
from src.proxy.logging import _build_errors_entries
from dev.refactoring.strand_runner import strand_workflow
from src.panes.warnings_pane import _errors_record_to_display
from src.panes.warnings_render import _build_one_warning_lines
from src.colors import DIM, SOFT_RESET, WHITE

_STRAND_NAMES = [
    '_test_mismatch_writes_exactly_one_sentence',
    '_test_equal_models_write_nothing',
    '_test_empty_answering_model_writes_nothing',
    '_test_double_write_guard',
    '_test_sentence_renders_through_real_pane_pipeline',
    '_test_signature_carries_no_dedup_state',
    '_test_interleaved_write_does_not_disturb_tool_use_id_dedup',
]
_TITLE = 'p10_model_mismatch_warning_test'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p10_model_mismatch_warning_test.md'

# ORCHESTRATOR

def run_model_mismatch_tests_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS


class _FakeHeaders(dict):
    def get(self, k, default=""):
        return dict.get(self, k, default)


class _FakeResponse:
    def __init__(self, status_code=200, request_id="req_1"):
        self.status_code = status_code
        self.headers = _FakeHeaders({"request-id": request_id, "content-type": "text/event-stream"})


class _FakePaths:
    def __init__(self, response_path, errors_path):
        self.response = response_path
        self.errors = errors_path


class _Identity:
    def __init__(self, session_id="sess123", worker_context="main"):
        self.session_id = session_id
        self.worker_context = worker_context


class _FakeFlow:
    def __init__(self, flow_id, cc_model, forwarded_model, answering_model, probe_done, request_id="req_1"):
        self.id = flow_id
        self.response = _FakeResponse(request_id=request_id)
        self.metadata = {
            "mc_original_payload": {"model": cc_model},
            "mc_modified_payload": {"model": forwarded_model},
            "mc_answering_model_state": {"model": answering_model, "done": probe_done},
        }


def _read_lines(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


@contextmanager
def _tmp_paths():
    with tempfile.TemporaryDirectory() as tmp:
        yield _FakePaths(Path(tmp) / "response.jsonl", Path(tmp) / "errors.jsonl")


def _test_mismatch_writes_exactly_one_sentence() -> None:
    with _tmp_paths() as paths:
        identity = _Identity()
        flow = _FakeFlow("flow-1", "claude-opus-4-6", "claude-opus-4-6", "claude-opus-4-6-fallback", True)
        _write_response_and_mismatch(flow, paths, identity)
        entries = _read_lines(paths.errors)
        assert len(entries) == 1, entries
        entry = entries[0]
        assert entry["type"] == "model_mismatch"
        assert entry["tool_name"] == "model_mismatch"
        assert entry["error_full"] == "model mismatch — requested claude-opus-4-6, answered claude-opus-4-6-fallback"
        assert entry["tool_use_id"] == ""
        assert entry["worker"] == "main"
        assert entry["session_id"] == "sess123"
        assert entry["request_id"] == "req_1"
        assert entry["flow_id"] == "flow-1"
        assert set(entry.keys()) == {
            "type", "request_id", "timestamp", "ts", "session_id", "worker",
            "tool_name", "tool_use_id", "error_full", "proxy_file", "flow_id",
        }


def _test_equal_models_write_nothing() -> None:
    with _tmp_paths() as paths:
        identity = _Identity()
        flow = _FakeFlow("flow-2", "claude-opus-4-6", "claude-opus-4-6", "claude-opus-4-6", True)
        _write_response_and_mismatch(flow, paths, identity)
        assert _read_lines(paths.errors) == []


def _test_empty_answering_model_writes_nothing() -> None:
    with _tmp_paths() as paths:
        identity = _Identity()
        flow = _FakeFlow("flow-3", "claude-opus-4-6", "claude-opus-4-6", "", False)
        _write_response_and_mismatch(flow, paths, identity)
        assert _read_lines(paths.errors) == [], (
            "an empty answering_model (abort before the first chunk) must not produce a sentence"
        )


def _test_double_write_guard() -> None:
    with _tmp_paths() as paths:
        identity = _Identity()
        flow = _FakeFlow("flow-4", "claude-opus-4-6", "claude-opus-4-6", "claude-opus-4-6-fallback", True)
        _write_response_and_mismatch(flow, paths, identity)
        _write_response_and_mismatch(flow, paths, identity)
        entries = _read_lines(paths.errors)
        assert len(entries) == 1, (
            "response()/error() are mutually exclusive per mitmproxy, but the guard must hold even if "
            f"both somehow fire for the same flow: {entries}"
        )


def _test_sentence_renders_through_real_pane_pipeline() -> None:

    with _tmp_paths() as paths:
        identity = _Identity()
        flow = _FakeFlow("flow-5", "claude-opus-4-6", "claude-opus-4-6", "claude-opus-4-6-fallback", True)
        _write_response_and_mismatch(flow, paths, identity)
        rec = _read_lines(paths.errors)[0]

        display = _errors_record_to_display(rec)
        assert display["tool_name"] == "model_mismatch"
        assert display["full_text"] == "model mismatch — requested claude-opus-4-6, answered claude-opus-4-6-fallback"
        assert display["timestamp"] != "00:00:00", (
            "the ts field must parse into a real time — a malformed timestamp silently renders as "
            "00:00:00 in format_timestamp, which is what this guards against"
        )

        lines, keys = _build_one_warning_lines(0, display, True, None, None, '', None, 100)
        assert len(lines) == 2
        assert f"{WHITE}{'model_mismatch':<16}{SOFT_RESET}" in lines[0]
        assert lines[1] == f"    {DIM}model mismatch — requested claude-opus-4-6, answered claude-opus-4-6-fallback{SOFT_RESET}"


def _test_signature_carries_no_dedup_state() -> None:
    params = list(inspect.signature(_write_model_mismatch_entry).parameters)
    assert 'seen_ids' not in params and 'delta_state' not in params and 'prev_seen_ids' not in params, (
        f"_write_model_mismatch_entry must never receive the tool_use_id dedup set — params were {params}"
    )


def _test_interleaved_write_does_not_disturb_tool_use_id_dedup() -> None:
    with _tmp_paths() as paths:
        identity = _Identity()

        payload = {
            "messages": [
                {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_X", "name": "Bash"}]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_X", "is_error": True, "content": "boom"},
                ]},
            ],
        }

        first_pass = _build_errors_entries(payload, "req_1", "2026-01-01T00:00:00.000Z", set(), "main", "sess123", "")
        assert len(first_pass) == 1 and first_pass[0]["tool_use_id"] == "toolu_X"
        seen_ids = {e["tool_use_id"] for e in first_pass}

        flow = _FakeFlow("flow-6", "claude-opus-4-6", "claude-opus-4-6", "claude-opus-4-6-fallback", True, request_id="req_2")
        _write_response_and_mismatch(flow, paths, identity)

        second_pass = _build_errors_entries(payload, "req_2", "2026-01-01T00:00:05.000Z", seen_ids, "main", "sess123", "")
        assert second_pass == [], (
            "the tool_use_id dedup must still suppress the already-seen error on the next request, "
            f"unaffected by the interleaved model_mismatch write: {second_pass}"
        )

        entries = _read_lines(paths.errors)
        assert len(entries) == 1 and entries[0]["type"] == "model_mismatch", (
            "the file must carry only the model_mismatch sentence here — this test never wrote the real "
            f"tool_error entry to the file (that happens via addon_dual_log._log_errors_entries, out of scope): {entries}"
        )


if __name__ == "__main__":
    run_model_mismatch_tests_workflow()
