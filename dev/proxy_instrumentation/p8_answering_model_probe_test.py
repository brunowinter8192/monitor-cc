# INFRASTRUCTURE
import gzip
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from src.proxy.response_model_probe import make_answering_model_probe, _MODEL_PROBE_BYTE_BUDGET
from dev.refactoring.strand_runner import strand_workflow

_SSE_MESSAGE_START = (
    b'event: message_start\n'
    b'data: {"type":"message_start","message":{"id":"msg_01ABC123","type":"message",'
    b'"role":"assistant","model":"claude-opus-4-6-20260701","content":[],'
    b'"stop_reason":null,"stop_sequence":null,'
    b'"usage":{"input_tokens":123,"output_tokens":1}}}\n\n'
)
_SSE_PING = b'event: ping\ndata: {"type":"ping"}\n\n'

_STRAND_NAMES = [
    '_test_single_chunk_finds_model',
    '_test_split_across_two_chunks_finds_model',
    '_test_pass_through_is_always_identity',
    '_test_budget_exceeded_stops_inspection',
    '_test_gzip_body_defeats_parsing',
]
_TITLE = 'p8_answering_model_probe_test'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p8_answering_model_probe_test.md'

# ORCHESTRATOR

def run_probe_tests_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS


def _test_single_chunk_finds_model() -> None:
    probe, state = make_answering_model_probe()
    returned = probe(_SSE_MESSAGE_START + _SSE_PING)
    assert returned == _SSE_MESSAGE_START + _SSE_PING
    assert state["model"] == "claude-opus-4-6-20260701", state
    assert state["done"] is True


def _test_split_across_two_chunks_finds_model() -> None:
    split_point = _SSE_MESSAGE_START.index(b'"model":"claude') + 20
    chunk_a = _SSE_MESSAGE_START[:split_point]
    chunk_b = _SSE_MESSAGE_START[split_point:]
    assert chunk_a and chunk_b

    probe, state = make_answering_model_probe()

    returned_a = probe(chunk_a)
    assert returned_a == chunk_a
    assert state["model"] == "", "model must not appear before the event completes"
    assert state["done"] is False

    returned_b = probe(chunk_b)
    assert returned_b == chunk_b
    assert state["model"] == "claude-opus-4-6-20260701", state
    assert state["done"] is True


def _test_pass_through_is_always_identity() -> None:
    probe, state = make_answering_model_probe()
    chunks = [
        b'event: message_start\ndata: {"type":"mess',
        b'age_start","message":{"model":"claude-son',
        b'net-4-6-20260701","id":"msg_02"}}\n\n',
        b'event: content_block_delta\ndata: {"delta":{"text":"hi"}}\n\n',
    ]
    for chunk in chunks:
        assert probe(chunk) == chunk
    assert state["model"] == "claude-sonnet-4-6-20260701"


def _test_budget_exceeded_stops_inspection() -> None:
    probe, state = make_answering_model_probe()
    filler = b'event: ping\ndata: {"type":"ping","pad":"' + b'x' * (_MODEL_PROBE_BYTE_BUDGET + 100) + b'"}\n\n'
    returned = probe(filler)
    assert returned == filler
    assert state["done"] is True
    assert state["model"] == ""

    late_message_start = _SSE_MESSAGE_START
    returned_late = probe(late_message_start)
    assert returned_late == late_message_start
    assert state["model"] == "", "inspection must stop once the byte budget is exceeded"


def _test_gzip_body_defeats_parsing() -> None:
    compressed = gzip.compress(_SSE_MESSAGE_START + _SSE_PING)
    probe, state = make_answering_model_probe()
    returned = probe(compressed)
    assert returned == compressed
    assert state["model"] == "", "compressed bytes must not spuriously match — documents the known gap"


if __name__ == "__main__":
    run_probe_tests_workflow()
