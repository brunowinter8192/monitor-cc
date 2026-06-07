# INFRASTRUCTURE
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from proxy.addon import _filter_response_headers  # noqa: E402

# FUNCTIONS

# Build a minimal mock of mitmproxy headers (case-insensitive dict-like via SimpleNamespace with items())
def _mock_headers(pairs: list) -> object:
    data = dict(pairs)

    class _Headers:
        def items(self):
            return data.items()
        def get(self, key, default=""):
            return data.get(key, default)

    return _Headers()


# Build a minimal mock flow for beta-flags extraction (request side)
def _mock_request_flow(beta_header: str) -> object:
    req = SimpleNamespace(headers=_mock_headers([("anthropic-beta", beta_header)]))
    return SimpleNamespace(request=req)


# ── beta-flags extraction tests ──────────────────────────────────────────────

def _extract_beta(beta_header: str) -> list:
    """Mirror the extraction logic in request() verbatim."""
    raw_beta = beta_header
    return [f.strip() for f in raw_beta.split(",") if f.strip()]


def test_beta_typical():
    result = _extract_beta("interleaved-thinking-2025-05-14,computer-use-2025-01-24,token-counting-2024-11-01")
    assert result == [
        "interleaved-thinking-2025-05-14",
        "computer-use-2025-01-24",
        "token-counting-2024-11-01",
    ], f"unexpected: {result}"


def test_beta_single():
    result = _extract_beta("pdfs-2024-09-25")
    assert result == ["pdfs-2024-09-25"], f"unexpected: {result}"


def test_beta_empty_header():
    result = _extract_beta("")
    assert result == [], f"expected empty list, got: {result}"


def test_beta_strips_whitespace():
    result = _extract_beta("flag-a , flag-b,  flag-c  ")
    assert result == ["flag-a", "flag-b", "flag-c"], f"unexpected: {result}"


def test_beta_drops_empty_segments():
    # comma with no content between (malformed header edge case)
    result = _extract_beta(",flag-a,,flag-b,")
    assert result == ["flag-a", "flag-b"], f"unexpected: {result}"


# ── _filter_response_headers tests ───────────────────────────────────────────

def test_filter_keeps_exact_request_id():
    h = _mock_headers([("request-id", "req_abc123"), ("content-type", "application/json")])
    result = _filter_response_headers(h)
    assert result == {"request-id": "req_abc123"}, f"unexpected: {result}"


def test_filter_keeps_retry_after_on_429():
    h = _mock_headers([
        ("retry-after", "30"),
        ("request-id", "req_xyz"),
        ("content-type", "application/json"),
        ("server", "nginx"),
    ])
    result = _filter_response_headers(h)
    assert result == {"retry-after": "30", "request-id": "req_xyz"}, f"unexpected: {result}"


def test_filter_keeps_ratelimit_family():
    pairs = [
        ("anthropic-ratelimit-requests-limit", "50"),
        ("anthropic-ratelimit-requests-remaining", "49"),
        ("anthropic-ratelimit-requests-reset", "2025-01-01T00:00:00Z"),
        ("anthropic-ratelimit-tokens-limit", "100000"),
        ("anthropic-ratelimit-tokens-remaining", "99000"),
        ("anthropic-ratelimit-tokens-reset", "2025-01-01T00:00:00Z"),
        ("anthropic-ratelimit-input-tokens-limit", "50000"),
        ("anthropic-ratelimit-output-tokens-limit", "10000"),
        ("content-type", "application/json"),
    ]
    h = _mock_headers(pairs)
    result = _filter_response_headers(h)
    assert "content-type" not in result
    assert "anthropic-ratelimit-requests-limit" in result
    assert result["anthropic-ratelimit-tokens-remaining"] == "99000"
    assert len(result) == 8, f"expected 8 rate-limit headers, got {len(result)}: {list(result)}"


def test_filter_keeps_organization_id():
    h = _mock_headers([
        ("anthropic-organization-id", "org-abc"),
        ("x-powered-by", "express"),
    ])
    result = _filter_response_headers(h)
    assert result == {"anthropic-organization-id": "org-abc"}, f"unexpected: {result}"


def test_filter_normalizes_to_lowercase():
    # mitmproxy may surface headers in original wire case
    h = _mock_headers([
        ("Request-Id", "req_mixed"),
        ("Retry-After", "60"),
        ("Anthropic-Ratelimit-Requests-Limit", "50"),
    ])
    result = _filter_response_headers(h)
    assert "request-id" in result
    assert "retry-after" in result
    assert "anthropic-ratelimit-requests-limit" in result
    # original mixed-case keys must NOT appear
    assert "Request-Id" not in result
    assert "Retry-After" not in result


def test_filter_prefix_anthropic_priority():
    h = _mock_headers([("anthropic-priority-queue", "high"), ("date", "Mon, 01 Jan 2025")])
    result = _filter_response_headers(h)
    assert result == {"anthropic-priority-queue": "high"}, f"unexpected: {result}"


def test_filter_prefix_anthropic_fast():
    h = _mock_headers([("anthropic-fast-tier", "1"), ("via", "1.1 proxy")])
    result = _filter_response_headers(h)
    assert result == {"anthropic-fast-tier": "1"}, f"unexpected: {result}"


def test_filter_empty_headers():
    h = _mock_headers([("content-type", "text/plain"), ("server", "nginx")])
    result = _filter_response_headers(h)
    assert result == {}, f"expected empty dict, got: {result}"


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_beta_typical,
        test_beta_single,
        test_beta_empty_header,
        test_beta_strips_whitespace,
        test_beta_drops_empty_segments,
        test_filter_keeps_exact_request_id,
        test_filter_keeps_retry_after_on_429,
        test_filter_keeps_ratelimit_family,
        test_filter_keeps_organization_id,
        test_filter_normalizes_to_lowercase,
        test_filter_prefix_anthropic_priority,
        test_filter_prefix_anthropic_fast,
        test_filter_empty_headers,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(0 if failed == 0 else 1)
