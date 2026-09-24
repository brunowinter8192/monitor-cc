# INFRASTRUCTURE
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.addon import _write_response_entry
from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    '_test_normal_completion_entry_shape',
    '_test_abort_before_first_chunk_still_writes_entry',
    '_test_abort_mid_stream_preserves_partial_probe_state',
    '_test_double_write_guard_prevents_duplicate',
    '_test_model_override_visible_via_three_distinct_fields',
]
_TITLE = 'p9_response_entry_abort_survival_test'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p9_response_entry_abort_survival_test.md'

# ORCHESTRATOR

def run_response_entry_tests_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS


class _FakeHeaders(dict):
    def get(self, k, default=""):
        return dict.get(self, k, default)


class _FakeResponse:
    def __init__(self, status_code=200, request_id="req_1", extra_headers=None):
        self.status_code = status_code
        headers = {"request-id": request_id, "content-type": "text/event-stream"}
        headers.update(extra_headers or {})
        self.headers = _FakeHeaders(headers)


class _FakeFlow:
    def __init__(self, flow_id="flow_1", cc_model="claude-opus-4-6",
                 forwarded_model="claude-opus-4-6", answering_model="", probe_done=False,
                 status_code=200, request_id="req_1"):
        self.id = flow_id
        self.response = _FakeResponse(status_code=status_code, request_id=request_id)
        self.metadata = {
            "mc_original_payload": {"model": cc_model},
            "mc_modified_payload": {"model": forwarded_model},
            "mc_answering_model_state": {"model": answering_model, "done": probe_done},
        }


@contextmanager
def _tmp_jsonl():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp) / "entries.jsonl"


def _read_entries(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _test_normal_completion_entry_shape() -> None:
    with _tmp_jsonl() as tmp:
        flow = _FakeFlow(answering_model="claude-opus-4-6", probe_done=True)
        _write_response_entry(flow, tmp)
        entries = _read_entries(tmp)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["cc_requested_model"] == "claude-opus-4-6"
        assert entry["proxy_forwarded_model"] == "claude-opus-4-6"
        assert entry["answering_model"] == "claude-opus-4-6"
        assert entry["request_id"] == "req_1"
        assert entry["status_code"] == 200
        assert set(entry.keys()) == {
            "flow_id", "timestamp", "request_id", "status_code", "headers",
            "cc_requested_model", "proxy_forwarded_model", "answering_model",
        }


def _test_abort_before_first_chunk_still_writes_entry() -> None:
    with _tmp_jsonl() as tmp:
        flow = _FakeFlow(flow_id="flow_abort_early", answering_model="", probe_done=False)
        _write_response_entry(flow, tmp)
        entries = _read_entries(tmp)
        assert len(entries) == 1, "an abort between responseheaders and the first chunk must still write an entry"
        assert entries[0]["answering_model"] == ""


def _test_abort_mid_stream_preserves_partial_probe_state() -> None:
    with _tmp_jsonl() as tmp:
        flow = _FakeFlow(flow_id="flow_abort_mid", answering_model="claude-opus-4-6-20260701", probe_done=True)
        _write_response_entry(flow, tmp)
        entries = _read_entries(tmp)
        assert len(entries) == 1
        assert entries[0]["answering_model"] == "claude-opus-4-6-20260701", (
            "message_start typically arrives in the first chunk — an abort later in the stream "
            "must not discard a model already captured by the probe"
        )


def _test_double_write_guard_prevents_duplicate() -> None:
    with _tmp_jsonl() as tmp:
        flow = _FakeFlow(flow_id="flow_double")
        _write_response_entry(flow, tmp)
        _write_response_entry(flow, tmp)
        entries = _read_entries(tmp)
        assert len(entries) == 1, (
            "mitmproxy guarantees exactly one of response/error per flow, but the guard must hold "
            "even if that invariant is ever violated"
        )


def _test_model_override_visible_via_three_distinct_fields() -> None:
    with _tmp_jsonl() as tmp:
        flow = _FakeFlow(
            flow_id="flow_override",
            cc_model="claude-opus-4-6",
            forwarded_model="claude-opus-4-6-fixed-override",
            answering_model="claude-opus-4-6-fixed-override",
            probe_done=True,
        )
        _write_response_entry(flow, tmp)
        entry = _read_entries(tmp)[0]
        assert entry["cc_requested_model"] == "claude-opus-4-6"
        assert entry["proxy_forwarded_model"] == "claude-opus-4-6-fixed-override"
        assert entry["answering_model"] == "claude-opus-4-6-fixed-override"
        assert entry["cc_requested_model"] != entry["proxy_forwarded_model"], (
            "the whole point of the three-field split: an active model override must be visible "
            "as a cc_requested_model/proxy_forwarded_model mismatch, not hidden behind one shared field"
        )


if __name__ == "__main__":
    run_response_entry_tests_workflow()
