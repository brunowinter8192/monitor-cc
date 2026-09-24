#!/usr/bin/env python3
# INFRASTRUCTURE
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src', 'hooks'))

from block_worker_kill_while_working import decide
from case_strands import case_runners, report_case, run_case_strands

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
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def make_stub(name_to_status: dict):
    def stub(name: str) -> str:
        if name == 'raises':
            raise RuntimeError("simulated status_fn error")
        return name_to_status.get(name, '')
    return stub


def _check_case(case: tuple) -> None:
    label, command, stub_map, expect = case
    block, name = decide(command, make_stub(stub_map))
    report_case(label, block == expect, f" (blocking: {name})" if block else "")


if __name__ == "__main__":
    test_block_worker_kill_while_working_workflow()
