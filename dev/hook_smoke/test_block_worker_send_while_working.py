#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src', 'hooks'))

from block_worker_send_while_working import decide
from case_strands import case_runners, function_runners, report_case, run_case_strands
from hook_runner import run_hook

HOOK = "src/hooks/block_worker_send_while_working.py"

CASES = [
    (
        "send working → block",
        "worker-cli send foo hello",
        {"foo": "working 88%"},
        True,
    ),
    (
        "send idle → allow",
        "worker-cli send foo hello",
        {"foo": "idle 59%"},
        False,
    ),
    (
        "send dead → allow",
        "worker-cli send foo hello",
        {"foo": "dead"},
        False,
    ),
    (
        "send unknown worker name (empty status) → allow",
        "worker-cli send foo hello",
        {"foo": ""},
        False,
    ),
    (
        "quoted send inside another send-message → allow (double-quoted region stripped)",
        'worker-cli send bar "worker-cli send foo hello"',
        {"foo": "working"},
        False,
    ),
    (
        "heredoc send inside send-message → allow (heredoc body stripped)",
        "worker-cli send bar <<EOF\nworker-cli send foo hello\nEOF",
        {"foo": "working"},
        False,
    ),
    (
        "non-send command → allow",
        "git status",
        {},
        False,
    ),
    (
        "multi-send one working → block (bar)",
        "worker-cli send foo hi && worker-cli send bar hi",
        {"foo": "idle 72%", "bar": "working 44%"},
        True,
    ),
    (
        "status_fn raises → allow (exception treated as empty status)",
        "worker-cli send raises hi",
        {},
        False,
    ),
    (
        "send working 100% → block",
        "worker-cli send foo hello",
        {"foo": "working 100%"},
        True,
    ),
]


# ORCHESTRATOR

def test_block_worker_send_while_working_workflow() -> None:
    sys.exit(run_case_strands(globals(), __file__, _all_runners()))


# FUNCTIONS

def make_stub(name_to_status: dict):
    def stub(name: str) -> str:
        if name == 'raises':
            raise RuntimeError("simulated status_fn error")
        return name_to_status.get(name, '')
    return stub


def _all_runners() -> dict:
    runners = case_runners(CASES, _check_case)
    runners.update(function_runners([_check_malformed_fails_open, _check_no_resolvable_worker]))
    return runners


def _check_case(case: tuple) -> None:
    label, command, stub_map, expect = case
    block, name = decide(command, make_stub(stub_map))
    report_case(label, block == expect, f" (blocking: {name})" if block else "")


def _check_malformed_fails_open() -> None:
    with tempfile.TemporaryDirectory(prefix="worker_send_fake_") as tmp:
        malformed = run_hook(HOOK, b"not valid json at all", extra_env=_fake_worker_cli_env(Path(tmp)))
    report_case("malformed stdin payload fails open", malformed.returncode == 0, f": exit={malformed.returncode} (expected 0)")


def _check_no_resolvable_worker() -> None:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "worker-cli send foo hi"}}).encode()
    with tempfile.TemporaryDirectory(prefix="worker_send_fake_") as tmp:
        no_worker = run_hook(HOOK, payload, extra_env=_fake_worker_cli_env(Path(tmp)))
    report_case("real entrypoint, no resolvable worker status", no_worker.returncode == 0, f": exit={no_worker.returncode} (expected 0)")


def _fake_worker_cli_env(tmp: Path) -> dict:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "worker-cli"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp)}


if __name__ == "__main__":
    test_block_worker_send_while_working_workflow()
