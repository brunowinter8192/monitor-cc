# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from case_strands import function_runners, run_case_strands
from hook_runner import abort_if_failed, run_hook

HOOK = "src/hooks/block_rag_cli_document_repeat.py"


# ORCHESTRATOR

def test_block_rag_cli_document_repeat_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, function_runners(_strand_functions())))


# FUNCTIONS

def _strand_functions() -> list:
    return [
        _test_single_document_call_allowed,
        _test_second_call_blocks,
        _test_collection_wide_always_allowed,
        _test_different_session_independent,
        _test_delete_subcommand_also_counts,
        _test_malformed_stdin_fail_open,
    ]


def _test_single_document_call_allowed() -> None:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        state = f.name
    try:
        got = _run_hook(
            "rag-cli index --collection monitor-cc-docs --document x.md",
            "sess-single", state,
        )
        status = "OK  " if got == 0 else "FAIL"
        print(f"  [{status}] single --document call ALLOW: exit={got} (expected 0)")
        if got != 0:
            failures.append("single --document call should pass")
            abort_if_failed(failures)
    finally:
        if os.path.exists(state):
            os.unlink(state)


def _run_hook(command: str, session_id: str, state_path: str) -> int:
    payload = json.dumps({
        "session_id": session_id,
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = run_hook(HOOK, payload.encode(), extra_env={"MONITOR_CC_RAG_DOC_REPEAT_STATE": state_path})
    return result.returncode


def _test_second_call_blocks() -> None:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        state = f.name
    try:
        first = _run_hook(
            "rag-cli index --collection monitor-cc-docs --document a.md",
            "sess-repeat", state,
        )
        second = _run_hook(
            "rag-cli index --collection monitor-cc-docs --document b.md",
            "sess-repeat", state,
        )
        status1 = "OK  " if first == 0 else "FAIL"
        status2 = "OK  " if second == 2 else "FAIL"
        print(f"  [{status1}] 1st --document call ALLOW: exit={first} (expected 0)")
        print(f"  [{status2}] 2nd --document call (same collection) BLOCK: exit={second} (expected 2)")
        if first != 0:
            failures.append("1st --document call should pass")
            abort_if_failed(failures)
        if second != 2:
            failures.append("2nd --document call to same collection should block")
            abort_if_failed(failures)
    finally:
        if os.path.exists(state):
            os.unlink(state)


def _test_collection_wide_always_allowed() -> None:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        state = f.name
    try:
        exits = [
            _run_hook("rag-cli index --collection monitor-cc-docs", "sess-wide", state)
            for _ in range(3)
        ]
        status = "OK  " if all(e == 0 for e in exits) else "FAIL"
        print(f"  [{status}] 3x collection-wide index call ALLOW: exits={exits} (expected all 0)")
        if not all(e == 0 for e in exits):
            failures.append("collection-wide calls should always pass")
            abort_if_failed(failures)
    finally:
        if os.path.exists(state):
            os.unlink(state)


def _test_different_session_independent() -> None:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        state = f.name
    try:
        a1 = _run_hook(
            "rag-cli delete --collection monitor-cc-docs --document a.md",
            "sess-A", state,
        )
        b1 = _run_hook(
            "rag-cli delete --collection monitor-cc-docs --document z.md",
            "sess-B", state,
        )
        a2 = _run_hook(
            "rag-cli delete --collection monitor-cc-docs --document b.md",
            "sess-A", state,
        )
        results_ok = a1 == 0 and b1 == 0 and a2 == 2
        status = "OK  " if results_ok else "FAIL"
        print(f"  [{status}] cross-session independence: sess-A#1={a1}, sess-B#1={b1}, "
              f"sess-A#2={a2} (expected 0, 0, 2)")
        if not results_ok:
            failures.append("session B's call should not count toward session A's counter")
            abort_if_failed(failures)
    finally:
        if os.path.exists(state):
            os.unlink(state)


def _test_delete_subcommand_also_counts() -> None:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        state = f.name
    try:
        first = _run_hook(
            "rag-cli delete --collection foo-docs --document a.md",
            "sess-delete", state,
        )
        second = _run_hook(
            "rag-cli delete --collection foo-docs --document b.md",
            "sess-delete", state,
        )
        results_ok = first == 0 and second == 2
        status = "OK  " if results_ok else "FAIL"
        print(f"  [{status}] delete subcommand 2nd call BLOCK: exits={first},{second} (expected 0,2)")
        if not results_ok:
            failures.append("delete subcommand should be covered same as index")
            abort_if_failed(failures)
    finally:
        if os.path.exists(state):
            os.unlink(state)


def _test_malformed_stdin_fail_open() -> None:
    failures = []
    result = run_hook(HOOK, b"not json at all {{{")
    got = result.returncode
    status = "OK  " if got == 0 else "FAIL"
    print(f"  [{status}] malformed stdin fail-open: exit={got} (expected 0)")
    if got != 0:
        failures.append("malformed stdin should fail open (exit 0)")
        abort_if_failed(failures)


if __name__ == "__main__":
    test_block_rag_cli_document_repeat_workflow()
