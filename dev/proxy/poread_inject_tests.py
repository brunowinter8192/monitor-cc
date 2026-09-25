# INFRASTRUCTURE
import hashlib
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.proxy.rules import apply_modification_rules
from src.proxy.inject_poread import _parse_poread_marker, _POREAD_HEADER_PREFIX
from src.proxy.strip_vocab import attribute_chunk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.strand_runner import strand_workflow

_PINNED_MARKER_PREFIX = '<poread-export '
_PINNED_HASH_LEN = 16
POREAD_NOTICE = (
    "The file's full content will arrive automatically on the next turn — do not read "
    "this file again until then."
)

_STRANDS = [
    'test_real_cli_marker_expands_to_full_content',
    'test_ops_path_and_attribution_both_sides',
    'test_determinism_across_two_runs',
    'test_file_changed_between_requests_leaves_marker_inert',
    'test_file_vanished_between_requests_leaves_marker_inert',
    'test_oversize_declared_marker_refused_regardless_of_actual_file',
    'test_marker_not_at_block_start_is_a_false_positive_and_untouched',
    'test_marker_with_trailing_content_is_untouched_not_truncated',
    'test_marker_alone_with_own_trailing_newline_still_expands',
    'test_source_is_read_only_once_per_marker',
    'test_marker_without_notice_is_ineligible',
    'test_marker_with_notice_expands_to_content',
]

# ORCHESTRATOR

def run_poread_inject_tests_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='poread_inject_tests')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _mint_marker(path: str) -> str:
    abs_path = os.path.realpath(path)
    with open(abs_path, 'rb') as f:
        data = f.read()
    digest = hashlib.sha256(data).hexdigest()[:_PINNED_HASH_LEN]
    marker = f'{_PINNED_MARKER_PREFIX}path="{abs_path}" bytes="{len(data)}" sha256="{digest}"/>'
    return f'{marker}\n{POREAD_NOTICE}'

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
    print("Item 1 - real poread marker expands to the file's full content")
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
    print("Item 2 - injection appears in the ops path, attributed to 'PR' on both sides")
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
    print("Item 3 - same marker, unchanged file, byte-identical injection across two separate runs")
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
    print("Item 4 - source file changed between two requests: second run injects nothing, marker stays as-is")
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
        check("the notice sentence is still present in r2 -- this is exactly the case where the "
              "agent needs the explanation, so it must not have been silently dropped",
              POREAD_NOTICE in r2)
    finally:
        os.unlink(path)

def test_file_vanished_between_requests_leaves_marker_inert():
    print("Item 5 - source file vanished between two requests: second run injects nothing")
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
    print("Item 6 - marker declaring over the ceiling is refused even if the real file is small")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"tiny actual file\n"
        f.write(data)
        path = f.name
    try:
        import hashlib
        fake_digest = hashlib.sha256(data).hexdigest()[:16]
        crafted_marker = f'<poread-export path="{path}" bytes="999999999" sha256="{fake_digest}"/>\n{POREAD_NOTICE}'
        payload = _payload_with_marker(crafted_marker)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("oversize-declared marker is refused (left unchanged)", result == crafted_marker)
        check("no mod recorded for the oversize-declared marker", "injected_poread_content" not in mods)
    finally:
        os.unlink(path)

def test_marker_not_at_block_start_is_a_false_positive_and_untouched():
    print("Item 7 - FP guard: marker text quoted mid-content (not block-initial) is left untouched")
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

def test_marker_with_trailing_content_is_untouched_not_truncated():
    print("Item 8 - trailing content after the marker in the same block is preserved, not lost: the marker must be the ENTIRE block or nothing is replaced")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"real content\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        trailing_content = marker + "\nsomething else the agent must not lose"
        payload = _payload_with_marker(trailing_content)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("block with trailing content left completely unchanged (nothing lost)", result == trailing_content)
        check("'something else' text is still present verbatim", "something else the agent must not lose" in result)
        check("no mod recorded when the marker is not the whole block", "injected_poread_content" not in mods)
    finally:
        os.unlink(path)

def test_marker_alone_with_own_trailing_newline_still_expands():
    print("Item 9 - regression guard: a marker with ONLY its own trailing newline (poread's real print() output shape) still expands normally")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"still expands\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        check("_mint_marker strips only the CLI's own FINAL trailing newline, keeping the one "
              "internal newline between the marker and the fixed notice sentence", marker.count('\n') == 1)
        payload = _payload_with_marker(marker + "\n")
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("marker plus its own trailing newline still expands", "injected_poread_content" in mods)
        check("expanded content carries the file's bytes", data.decode('utf-8') in result)
    finally:
        os.unlink(path)

def test_source_is_read_only_once_per_marker():
    print("Item 10 - the file is opened exactly once per validated marker (predicate result feeds the replacement directly; no second read, no race window between the two)")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"read exactly once\n"
        f.write(data)
        path = f.name
    try:
        marker = _mint_marker(path)
        payload = _payload_with_marker(marker)

        from src.proxy import inject_poread as inject_poread_mod
        open_calls = []
        real_open = open

        real_path = os.path.realpath(path)

        def _counting_open(p, *a, **kw):
            if p == real_path:
                open_calls.append(p)
            return real_open(p, *a, **kw)

        inject_poread_mod.open = _counting_open
        try:
            modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        finally:
            del inject_poread_mod.open

        result = modified["messages"][2]["content"][0]["content"]
        check("expansion still succeeds", "injected_poread_content" in mods and data.decode('utf-8') in result)
        check("the source file was opened exactly once for this one marker", len(open_calls) == 1)
    finally:
        os.unlink(path)

def test_marker_without_notice_is_ineligible():
    print("Item 11 - a marker with no notice sentence under it is ineligible for expansion (the "
          "notice is now part of the whole-block contract, not an optional extra line)")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"content that must not be injected without the notice\n"
        f.write(data)
        path = f.name
    try:
        import hashlib
        digest = hashlib.sha256(data).hexdigest()[:16]
        marker_only = f'<poread-export path="{os.path.realpath(path)}" bytes="{len(data)}" sha256="{digest}"/>'
        payload = _payload_with_marker(marker_only)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("marker without the notice is left completely unchanged", result == marker_only)
        check("no mod recorded for a marker missing the notice", "injected_poread_content" not in mods)
    finally:
        os.unlink(path)

def test_marker_with_notice_expands_to_content():
    print("Item 12 - marker plus the exact fixed notice sentence expands to the file's full "
          "content, and the notice itself disappears along with the marker (the 'expansion "
          "succeeded' property, for free from the same full_replace mechanics)")
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        data = b"content that DOES get injected once the notice is present\n"
        f.write(data)
        path = f.name
    try:
        import hashlib
        digest = hashlib.sha256(data).hexdigest()[:16]
        marker_plus_notice = f'<poread-export path="{os.path.realpath(path)}" bytes="{len(data)}" sha256="{digest}"/>\n{POREAD_NOTICE}'
        payload = _payload_with_marker(marker_plus_notice)
        modified, mods, *_ = apply_modification_rules(payload, "opus", "", "main")
        result = modified["messages"][2]["content"][0]["content"]
        check("mod recorded once the exact notice is present", "injected_poread_content" in mods)
        check("the notice text is gone from the result -- replaced along with the marker, not appended to", POREAD_NOTICE not in result)
        check("result carries the exact file content", data.decode('utf-8') in result)
    finally:
        os.unlink(path)

if __name__ == '__main__':
    sys.exit(run_poread_inject_tests_workflow())
