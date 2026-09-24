# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))

from proxy.addon_dual_log import _is_sidecar_payload, _write_request_dual_logs
from proxy.addon_state import DeltaState, DualLogPaths, SessionIdentity

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("sidecar delta-chain isolation probe (src/proxy/addon_dual_log.py)")
    print("=" * 70)
    test_is_sidecar_payload_matches_tool_count()
    test_sidecar_does_not_advance_chain_and_next_real_diffs_against_last_real()
    test_real_change_after_sidecar_still_reported()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)
    return passed == total


# FUNCTIONS

class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


class _FakeFlow:
    def __init__(self, flow_id, headers=None):
        self.id = flow_id
        self.request = _FakeRequest(headers or {})


def _payload(model, tools, system_texts, msg_text="hi"):
    return {
        "model": model,
        "tools": tools,
        "system": [{"type": "text", "text": t} for t in system_texts],
        "messages": [{"role": "user", "content": msg_text}],
    }


def _make_paths(tmp_dir: Path) -> DualLogPaths:
    return DualLogPaths(
        original=tmp_dir / "original.jsonl",
        forwarded=tmp_dir / "forwarded.jsonl",
        stripped=tmp_dir / "stripped.jsonl",
        injected=tmp_dir / "injected.jsonl",
        errors=tmp_dir / "errors.jsonl",
        response=tmp_dir / "response.jsonl",
    )


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _real_and_sidecar_payloads():
    real_payload = _payload(
        "claude-opus-4-8", [{"name": "Bash"}, {"name": "Read"}],
        ["billing header", "You are Claude Code, Anthropic's official CLI."],
    )
    sidecar_payload = _payload(
        "claude-opus-4-8", [],
        ["You are naming a coding session so the user can pick it out of a long list."],
        msg_text="<session>fix the bug</session>",
    )
    return real_payload, sidecar_payload


def test_is_sidecar_payload_matches_tool_count():
    print("\n[Test 1] _is_sidecar_payload: tools-count-zero, model-agnostic")
    check("empty tools list -> sidecar", _is_sidecar_payload({"tools": []}))
    check("missing tools key -> sidecar", _is_sidecar_payload({}))
    check("one tool -> not sidecar", not _is_sidecar_payload({"tools": [{"name": "Bash"}]}))
    check("six tools -> not sidecar", not _is_sidecar_payload({"tools": [{"name": f"T{i}"} for i in range(6)]}))


def test_sidecar_does_not_advance_chain_and_next_real_diffs_against_last_real():
    print("\n[Test 2] Sidecar write does not advance the per-family chain")
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        paths = _make_paths(tmp_dir)
        delta_state = DeltaState()
        identity = SessionIdentity(session_id="s", worker_context="main")
        real_payload, sidecar_payload = _real_and_sidecar_payloads()

        _write_request_dual_logs(
            _FakeFlow("f1"), real_payload, real_payload, "opus", "req1", "ts1",
            paths, delta_state, identity,
        )
        state_after_real1 = dict(delta_state.forwarded_hashes_by_model.get("opus", {}))
        check("first real request seeds the opus chain", bool(state_after_real1))

        _write_request_dual_logs(
            _FakeFlow("sidecar"), sidecar_payload, sidecar_payload, "opus", "req2", "ts2",
            paths, delta_state, identity,
        )
        check(
            "sidecar write does NOT change forwarded_hashes_by_model['opus']",
            delta_state.forwarded_hashes_by_model.get("opus") == state_after_real1,
        )

        _write_request_dual_logs(
            _FakeFlow("f2"), real_payload, real_payload, "opus", "req3", "ts3",
            paths, delta_state, identity,
        )

        fwd_entries = _read_jsonl(paths.forwarded)
        check("3 forwarded_delta lines written (sidecar IS still logged)", len(fwd_entries) == 3)
        last_entry = fwd_entries[-1]
        check("last (real, byte-identical to REQ1) entry has an empty system_delta",
              last_entry.get("system_delta") == {})
        check("last (real, byte-identical to REQ1) entry has an empty tools_delta",
              last_entry.get("tools_delta") == {})
        check("last entry is not marked is_first", last_entry.get("is_first") is False)

        sidecar_entry = fwd_entries[1]
        check("the sidecar's own forwarded_delta line still carries counts.tools == 0 "
              "(the artifact-level marker a reader identifies it by)",
              (sidecar_entry.get("counts") or {}).get("tools") == 0)


def test_real_change_after_sidecar_still_reported():
    print("\n[Test 3] A genuine change after a sidecar is still visible in forwarded_delta")
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        paths = _make_paths(tmp_dir)
        delta_state = DeltaState()
        identity = SessionIdentity(session_id="s", worker_context="main")

        real_payload_1 = _payload("claude-opus-4-8", [{"name": "Bash"}], ["sys prompt v1"])
        sidecar_payload = _payload("claude-opus-4-8", [], ["quota check prompt"], msg_text="quota")
        real_payload_2 = _payload("claude-opus-4-8", [{"name": "Bash"}, {"name": "Read"}], ["sys prompt v1"])

        _write_request_dual_logs(_FakeFlow("f1"), real_payload_1, real_payload_1, "opus", "r1", "t1",
                                  paths, delta_state, identity)
        _write_request_dual_logs(_FakeFlow("sidecar"), sidecar_payload, sidecar_payload, "opus", "r2", "t2",
                                  paths, delta_state, identity)
        _write_request_dual_logs(_FakeFlow("f2"), real_payload_2, real_payload_2, "opus", "r3", "t3",
                                  paths, delta_state, identity)

        fwd_entries = _read_jsonl(paths.forwarded)
        last_entry = fwd_entries[-1]
        check("the real REQ 2 tools change (Bash -> Bash,Read) is reported",
              "1" in last_entry.get("tools_delta", {}))
        check("REQ 2's new tool is Read, not something sidecar-derived",
              (last_entry["tools_delta"]["1"] or {}).get("name") == "Read")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
