#!/usr/bin/env python3
import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src', 'hooks'))

from block_worker_send_while_working import decide

HOOK = "src/hooks/block_worker_send_while_working.py"


def make_stub(name_to_status: dict):
    def stub(name: str) -> str:
        if name == 'raises':
            raise RuntimeError("simulated status_fn error")
        return name_to_status.get(name, '')
    return stub


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

malformed_result = subprocess.run(
    ["python3", HOOK], input=b"not valid json at all", capture_output=True,
)
ok = malformed_result.returncode == 0
mark = "PASS" if ok else "FAIL"
print(f"[{mark}] malformed stdin payload fails open: exit={malformed_result.returncode} (expected 0)")
if ok:
    passed += 1
else:
    failed += 1

no_worker_result = subprocess.run(
    ["python3", HOOK],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "worker-cli send foo hi"}}).encode(),
    capture_output=True,
)
ok = no_worker_result.returncode == 0
mark = "PASS" if ok else "FAIL"
print(f"[{mark}] real entrypoint, no resolvable worker status: exit={no_worker_result.returncode} (expected 0)")
if ok:
    passed += 1
else:
    failed += 1

print(f"\n{passed}/{passed + failed} passed")
sys.exit(0 if failed == 0 else 1)
