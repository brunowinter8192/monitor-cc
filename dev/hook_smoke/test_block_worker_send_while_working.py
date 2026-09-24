#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src', 'hooks'))

from block_worker_send_while_working import decide
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
    passed, failed = _run_cases()
    if failed:
        _report_and_exit(passed, failed)
    entry_passed, entry_failed = _run_entrypoint_cases()
    _report_and_exit(passed + entry_passed, failed + entry_failed)


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
            break
    return passed, failed


def _run_entrypoint_cases() -> tuple:
    with tempfile.TemporaryDirectory(prefix="worker_send_fake_") as tmp:
        fake_env = _fake_worker_cli_env(Path(tmp))
        malformed = run_hook(HOOK, b"not valid json at all", extra_env=fake_env)
        no_worker = run_hook(
            HOOK,
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "worker-cli send foo hi"}}).encode(),
            extra_env=fake_env,
        )
    results = [
        ("malformed stdin payload fails open", malformed.returncode),
        ("real entrypoint, no resolvable worker status", no_worker.returncode),
    ]
    passed = failed = 0
    for label, code in results:
        ok = code == 0
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: exit={code} (expected 0)")
        if ok:
            passed += 1
        else:
            failed += 1
            break
    return passed, failed


def _fake_worker_cli_env(tmp: Path) -> dict:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "worker-cli"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp)}


def _report_and_exit(passed: int, failed: int) -> None:
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    test_block_worker_send_while_working_workflow()
