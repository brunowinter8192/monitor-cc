# INFRASTRUCTURE
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.addon import _request_identity_encoding

# ORCHESTRATOR

def run_identity_encoding_tests_workflow() -> None:
    _test_sets_accept_encoding_identity_from_empty()
    _test_overwrites_existing_accept_encoding_value()
    print("[p11_request_identity_encoding_test] all checks passed")

# FUNCTIONS


class _FakeHeaders(dict):
    pass


class _FakeRequest:
    def __init__(self, headers=None):
        self.headers = _FakeHeaders(headers or {})


class _FakeFlow:
    def __init__(self, headers=None):
        self.request = _FakeRequest(headers)


def _test_sets_accept_encoding_identity_from_empty() -> None:
    flow = _FakeFlow()
    _request_identity_encoding(flow)
    assert flow.request.headers["accept-encoding"] == "identity", flow.request.headers


def _test_overwrites_existing_accept_encoding_value() -> None:
    flow = _FakeFlow(headers={"accept-encoding": "gzip, br"})
    _request_identity_encoding(flow)
    assert flow.request.headers["accept-encoding"] == "identity", (
        "the outbound request's compressed accept-encoding must be overwritten, not merged or "
        f"left alone, or the API can still choose to answer compressed: {flow.request.headers}"
    )


if __name__ == "__main__":
    run_identity_encoding_tests_workflow()
