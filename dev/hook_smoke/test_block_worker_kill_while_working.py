#!/usr/bin/env python3
# INFRASTRUCTURE
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src', 'hooks'))

from block_worker_kill_while_working import decide

CASES = [
    (
        "kill working → block",
        "worker-cli kill foo",
        {"foo": "working 88%"},
        True,
    ),
    (
        "kill idle → allow",
        "worker-cli kill foo",
        {"foo": "idle 59%"},
        False,
    ),
    (
        "kill force-stopped idle (no pct) → allow",
        "worker-cli kill foo",
        {"foo": "idle"},
        False,
    ),
    (
        "kill exited → allow",
        "worker-cli kill foo",
        {"foo": "exited —%"},
        False,
    ),
    (
        "kill unknown → allow",
        "worker-cli kill foo",
        {"foo": "unknown"},
        False,
    ),
    (
        "kill nonexistent (empty status) → allow",
        "worker-cli kill foo",
        {"foo": ""},
        False,
    ),
    (
        "quoted kill inside send-message → allow (double-quoted region stripped)",
        'worker-cli send bar "worker-cli kill foo"',
        {"foo": "working"},
        False,
    ),
    (
        "heredoc kill inside send-message → allow (heredoc body stripped)",
        "worker-cli send bar <<EOF\nworker-cli kill foo\nEOF",
        {"foo": "working"},
        False,
    ),
    (
        "non-kill command → allow",
        "git status",
        {},
        False,
    ),
    (
        "multi-kill one working → block (bar)",
        "worker-cli kill foo && worker-cli kill bar",
        {"foo": "idle 72%", "bar": "working 44%"},
        True,
    ),
    (
        "status_fn raises → allow (exception treated as empty status)",
        "worker-cli kill raises",
        {},
        False,
    ),
    (
        "kill working 100% → block",
        "worker-cli kill foo",
        {"foo": "working 100%"},
        True,
    ),
    (
        "known accepted residual: comment carrying kill+working-name → block",
        "echo hi # worker-cli kill foo",
        {"foo": "working"},
        True,
    ),
]


# ORCHESTRATOR

def test_block_worker_kill_while_working_workflow() -> None:
    passed, failed = _run_cases()
    _report_and_exit(passed, failed)


# FUNCTIONS

def make_stub(name_to_status: dict):
    def stub(name: str) -> str:
        if name == 'raises':
            raise RuntimeError("simulated status_fn error")
        return name_to_status.get(name, '')
    return stub


def _run_cases() -> tuple:
    passed = failed = 0
    for label, cmd, stub_map, expect in CASES:
        block, name = decide(cmd, make_stub(stub_map))
        ok = (block == expect)
        mark = "PASS" if ok else "FAIL"
        blocking_info = f" (blocking: {name})" if block else ""
        print(f"[{mark}] {label}{blocking_info}")
        if ok:
            passed += 1
        else:
            failed += 1
    return passed, failed


def _report_and_exit(passed: int, failed: int) -> None:
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    test_block_worker_kill_while_working_workflow()
