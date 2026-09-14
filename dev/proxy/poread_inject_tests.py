"""Regression suite for src/proxy/inject_poread.py (the poread marker-expansion pass).

Covers: a marker minted by the REAL poread CLI (invoked as a real subprocess, not reimplemented)
expands to the file's full content when run through the real apply_modification_rules pipeline;
the injection shows up in the ops path (all_ops) and in strip_vocab.attribute_chunk on BOTH the
stripped (marker) and injected (wrapped content) sides; the expansion is byte-identical across two
separate pipeline runs against the same unchanged file (determinism); a source file that changed
or vanished between two runs leaves the marker completely inert (no mods, no ops, original text
preserved) rather than injecting stale or wrong content; a marker whose declared byte count exceeds
the 500,000-byte ceiling is refused regardless of what the actual file contains; a marker that is
NOT the first thing in its block (mid-content, false-positive class) is left untouched; a realistic
multi-message payload shape (system + user prompt + assistant tool_use + user tool_result carrying
the marker) exercises the full apply_modification_rules pass order end to end.

Run from project root:
    ./venv/bin/python dev/proxy/poread_inject_tests.py
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
_WORKTREE_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')

from proxy.rules import apply_modification_rules
from proxy.inject_poread import _parse_poread_marker, _POREAD_HEADER_PREFIX
from proxy.strip_vocab import attribute_chunk

_PASS = "PASS"
_FAIL = "FAIL"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


def _mint_marker(path: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "src.poread_cli", path],
        cwd=_WORKTREE_ROOT, capture_output=True, text=True, check=True,
    )
    assert proc.stdout.count('\n') == 1, f"poread stdout must be exactly one line: {proc.stdout!r}"
    return proc.stdout.rstrip('\n')


def _payload_with_marker(marker: str) -> dict:
    return {
        "model": "claude-opus-4-6",
        "system": [{"type": "text", "text": "boilerplate"}],
        "messages": [
            {"role": "user", "content": "please read this file fully"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_01", "name": "Bash", "input": {"command": "poread /tmp/x"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_01", "content": marker},
            ]},
        ],
    }


def test_real_cli_marker_expands_to_full_content():
    print("Item 1 — real poread marker expands to the file's full content")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"full file content\nspanning multiple lines\nfor the agent to read\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        payload = _payload_with_marker(marker)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("mod recorded", "injected_poread_content" in mods)
        check("result carries the poread header", result.startswith(_POREAD_HEADER_PREFIX))
        check("result carries the exact file content", data.decode('utf-8') in result)
        check("result carries the resolved path", os.path.realpath(path) in result)
    finally:
        os.unlink(path)


def test_ops_path_and_attribution_both_sides():
    print("Item 2 — injection appears in the ops path, attributed to 'PR' on both sides")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"ops-path content\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        payload = _payload_with_marker(marker)
        modified, mods, orig_sys2, smi, smo, smr, ima, all_ops = apply_modification_rules(payload, "opus", "", "main")
        block_ops = all_ops.get(2, {}).get(0, [])
        check("exactly one op recorded", len(block_ops) == 1)
        offset, removed, injected = block_ops[0]
        check("op offset is 0 (full_replace)", offset == 0)
        check("op removed is the original marker", removed == marker)
        check("op injected is the full replacement", injected.startswith(_POREAD_HEADER_PREFIX) and data.decode('utf-8') in injected)
        check("stripped-side attribution resolves to PR", attribute_chunk(marker) == 'PR')
        check("injected-side attribution resolves to PR", attribute_chunk(injected) == 'PR')
    finally:
        os.unlink(path)


def test_determinism_across_two_runs():
    print("Item 3 — same marker, unchanged file, byte-identical injection across two separate runs")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"stable content that must not drift\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        payload = _payload_with_marker(marker)
        modified1, mods1, *_ = apply_modification_rules(payload, "opus", "", "main")
        modified2, mods2, *_ = apply_modification_rules(payload, "opus", "", "main")
        r1 = modified1["messages"][2]["content"][0]["content"]
        r2 = modified2["messages"][2]["content"][0]["content"]
        check("mods identical across both runs", mods1 == mods2)
        check("injected bytes identical across both runs", r1 == r2)
    finally:
        os.unlink(path)


def test_file_changed_between_requests_leaves_marker_inert():
    print("Item 4 — source file changed between two requests: second run injects nothing, marker stays as-is")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"version one of the file\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        payload = _payload_with_marker(marker)
        modified1, mods1, *_ = apply_modification_rules(payload, "opus", "", "main")
        r1 = modified1["messages"][2]["content"][0]["content"]
        check("first run (unchanged file) injects real content", r1 != marker and data.decode('utf-8') in r1)

        with open(path, 'wb') as f2:
            f2.write(b"version TWO -- different content, same or different size\n")

        modified2, mods2, orig_sys2, smi, smo, smr, ima, all_ops2 = apply_modification_rules(payload, "opus", "", "main")
        r2 = modified2["messages"][2]["content"][0]["content"]
        check("second run (changed file) leaves marker completely unchanged", r2 == marker)
        check("second run records no mod for this pass", "injected_poread_content" not in mods2)
        check("second run records no op for this block", all_ops2.get(2, {}).get(0, []) == [])
    finally:
        os.unlink(path)


def test_file_vanished_between_requests_leaves_marker_inert():
    print("Item 5 — source file vanished between two requests: second run injects nothing")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"will be deleted\n"
        f.write(data)
        path = f.name
    marker = _mint_marker(path)
    payload = _payload_with_marker(marker)
    modified1, mods1, *_ = apply_modification_rules(payload, "opus", "", "main")
    r1 = modified1["messages"][2]["content"][0]["content"]
    check("first run injects real content", data.decode('utf-8') in r1)

    os.unlink(path)

    modified2, mods2, *_ = apply_modification_rules(payload, "opus", "", "main")
    r2 = modified2["messages"][2]["content"][0]["content"]
    check("second run (vanished file) leaves marker unchanged", r2 == marker)
    check("second run records no mod", "injected_poread_content" not in mods2)


def test_oversize_declared_marker_refused_regardless_of_actual_file():
    print("Item 6 — marker declaring over the ceiling is refused even if the real file is small")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"tiny actual file\n"
        f.write(data)
        path = f.name
    try:
        import hashlib
        fake_digest = hashlib.sha256(data).hexdigest()[:16]
        crafted_marker = f'<poread-export path="{path}" bytes="999999999" sha256="{fake_digest}"/>'
        payload = _payload_with_marker(crafted_marker)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("oversize-declared marker is refused (left unchanged)", result == crafted_marker)
        check("no mod recorded for the oversize-declared marker", "injected_poread_content" not in mods)
    finally:
        os.unlink(path)


def test_marker_not_at_block_start_is_a_false_positive_and_untouched():
    print("Item 7 — FP guard: marker text quoted mid-content (not block-initial) is left untouched")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"real content\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        mid_content = "Some earlier output line.\n" + marker
        payload = _payload_with_marker(mid_content)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("mid-content marker left completely unchanged", result == mid_content)
        check("no mod recorded for a non-block-initial marker", "injected_poread_content" not in mods)
    finally:
        os.unlink(path)


# ORCHESTRATOR

def run_poread_inject_tests_workflow() -> None:
    test_real_cli_marker_expands_to_full_content()
    test_ops_path_and_attribution_both_sides()
    test_determinism_across_two_runs()
    test_file_changed_between_requests_leaves_marker_inert()
    test_file_vanished_between_requests_leaves_marker_inert()
    test_oversize_declared_marker_refused_regardless_of_actual_file()
    test_marker_not_at_block_start_is_a_false_positive_and_untouched()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    run_poread_inject_tests_workflow()
