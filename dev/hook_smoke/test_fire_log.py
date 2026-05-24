# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile

HOOK_DIR = "src/hooks"
BLOCK_HOOK = f"{HOOK_DIR}/block_noop_edit.py"
REWRITE_HOOK = f"{HOOK_DIR}/rewrite_git_ambiguous.py"


# ORCHESTRATOR

# Run all fire-log tests; exit 1 if any fail
def test_fire_log_workflow() -> None:
    failures = []

    failures.extend(_test_block_fire())
    failures.extend(_test_rewrite_fire())
    failures.extend(_test_env_var_override())
    failures.extend(_test_tool_error_writer())

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All fire-log tests passed.")


# FUNCTIONS

# Run a hook via subprocess with a given log path env var; return (exit_code, log_line_or_None)
def _run_hook(hook: str, payload: dict, log_path: str) -> tuple:
    env = dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=log_path)
    result = subprocess.run(
        ["python3", hook],
        input=json.dumps(payload).encode(),
        capture_output=True,
        env=env,
    )
    line = None
    if os.path.exists(log_path):
        lines = [l for l in open(log_path).read().splitlines() if l.strip()]
        if lines:
            try:
                line = json.loads(lines[-1])
            except json.JSONDecodeError:
                line = None
    return result.returncode, line


# Block fire test: block_noop_edit with old_string == new_string → decision=block
def _test_block_fire() -> list:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = f.name
    try:
        payload = {
            "session_id": "test-sess-001",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/test.py",
                "old_string": "same content",
                "new_string": "same content",
            },
        }
        exit_code, rec = _run_hook(BLOCK_HOOK, payload, tmp)
        if exit_code != 2:
            failures.append(f"block fire: expected exit 2, got {exit_code}")
        elif rec is None:
            failures.append("block fire: no log line written")
        else:
            if rec.get("decision") != "block":
                failures.append(f"block fire: expected decision=block, got {rec.get('decision')}")
            if rec.get("hook") != "block_noop_edit":
                failures.append(f"block fire: expected hook=block_noop_edit, got {rec.get('hook')}")
            if rec.get("tool") != "Edit":
                failures.append(f"block fire: expected tool=Edit, got {rec.get('tool')}")
            if rec.get("session") != "test-sess-001":
                failures.append(f"block fire: expected session=test-sess-001, got {rec.get('session')}")
            if "reason" not in rec:
                failures.append("block fire: missing 'reason' field")
            if "rewritten" in rec:
                failures.append("block fire: unexpected 'rewritten' field on block record")
            status = "OK  " if not [x for x in failures if "block fire" in x] else "FAIL"
            print(f"  [{status}] block fire: decision=block, hook=block_noop_edit, tool=Edit")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return failures


# Rewrite fire test: rewrite_git_ambiguous with 'git diff dev' → decision=rewrite, both fields present
def _test_rewrite_fire() -> list:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = f.name
    try:
        payload = {
            "session_id": "test-sess-002",
            "tool_name": "Bash",
            "tool_input": {"command": "git diff dev"},
        }
        exit_code, rec = _run_hook(REWRITE_HOOK, payload, tmp)
        if exit_code != 0:
            failures.append(f"rewrite fire: expected exit 0, got {exit_code}")
        elif rec is None:
            failures.append("rewrite fire: no log line written")
        else:
            if rec.get("decision") != "rewrite":
                failures.append(f"rewrite fire: expected decision=rewrite, got {rec.get('decision')}")
            if rec.get("hook") != "rewrite_git_ambiguous":
                failures.append(f"rewrite fire: expected hook=rewrite_git_ambiguous, got {rec.get('hook')}")
            if rec.get("command") != "git diff dev":
                failures.append(f"rewrite fire: expected command='git diff dev', got {rec.get('command')}")
            if not rec.get("rewritten"):
                failures.append("rewrite fire: missing or empty 'rewritten' field")
            if "reason" in rec:
                failures.append("rewrite fire: unexpected 'reason' field on rewrite record")
            if rec.get("session") != "test-sess-002":
                failures.append(f"rewrite fire: expected session=test-sess-002, got {rec.get('session')}")
            status = "OK  " if not [x for x in failures if "rewrite fire" in x] else "FAIL"
            print(f"  [{status}] rewrite fire: decision=rewrite, command+rewritten both present")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return failures


# Env-var override test: log written to custom path, NOT to canonical path
def _test_env_var_override() -> list:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        custom_tmp = f.name
    canonical_tmp = tempfile.mktemp(suffix="_canonical.jsonl")
    try:
        # Use custom path via env var; canonical path is a different temp path (should NOT be written)
        env = dict(os.environ, MONITOR_CC_HOOK_FIRING_LOG=custom_tmp)
        payload = {
            "session_id": "test-sess-003",
            "tool_name": "Bash",
            "tool_input": {"command": "git diff dev"},
        }
        subprocess.run(
            ["python3", REWRITE_HOOK],
            input=json.dumps(payload).encode(),
            capture_output=True,
            env=env,
        )
        written_to_custom = os.path.exists(custom_tmp) and os.path.getsize(custom_tmp) > 0
        written_to_canonical = os.path.exists(canonical_tmp) and os.path.getsize(canonical_tmp) > 0
        if not written_to_custom:
            failures.append("env-var override: nothing written to custom path")
        if written_to_canonical:
            failures.append("env-var override: unexpectedly written to canonical path")
        status = "OK  " if not [x for x in failures if "env-var override" in x] else "FAIL"
        print(f"  [{status}] env-var override: log written to custom path, canonical untouched")
    finally:
        if os.path.exists(custom_tmp):
            os.unlink(custom_tmp)
        if os.path.exists(canonical_tmp):
            os.unlink(canonical_tmp)
    return failures


# Tool-error writer unit test: call append_tool_errors with a synthetic error dict, verify JSONL output
def _test_tool_error_writer() -> list:
    failures = []
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = f.name
    try:
        os.environ["MONITOR_CC_TOOL_ERROR_LOG"] = tmp
        # Import the writer from the src package
        sys.path.insert(0, os.path.abspath("."))
        from src.panes.warnings_persist import append_tool_errors
        synthetic_error = {
            'timestamp': '14:30:22',
            '_ts_raw': '2026-05-24T14:30:22Z',
            'tool_name': 'Bash',
            '_tool_use_id': 'toolu_abc123',
            'full_text': 'File does not exist. Note: your current working directory is /tmp',
            'worker_name': 'audit-logging',
            '_proxy_file': 'api_requests_worker_abcd1234_audit-logging_20260524.jsonl',
            '_request_id': 'req-xyz789',
        }
        append_tool_errors([synthetic_error], project_filter='')
        lines = [l for l in open(tmp).read().splitlines() if l.strip()]
        if not lines:
            failures.append("tool-error writer: no line written")
        else:
            rec = json.loads(lines[0])
            if rec.get("tool_name") != "Bash":
                failures.append(f"tool-error writer: expected tool_name=Bash, got {rec.get('tool_name')}")
            if rec.get("worker") != "worker:audit-logging":
                failures.append(f"tool-error writer: expected worker=worker:audit-logging, got {rec.get('worker')}")
            if rec.get("tool_use_id") != "toolu_abc123":
                failures.append(f"tool-error writer: expected tool_use_id=toolu_abc123, got {rec.get('tool_use_id')}")
            if rec.get("ts") != "2026-05-24T14:30:22Z":
                failures.append(f"tool-error writer: expected ts=2026-05-24T14:30:22Z, got {rec.get('ts')}")
            if "File does not exist" not in rec.get("error_full", ""):
                failures.append("tool-error writer: error_full missing expected text")
            if rec.get("request_id") != "req-xyz789":
                failures.append(f"tool-error writer: expected request_id=req-xyz789, got {rec.get('request_id')}")
        status = "OK  " if not [x for x in failures if "tool-error writer" in x] else "FAIL"
        print(f"  [{status}] tool-error writer: JSONL line verified (tool_name, worker, ts, tool_use_id, error_full, request_id)")
    finally:
        del os.environ["MONITOR_CC_TOOL_ERROR_LOG"]
        if os.path.exists(tmp):
            os.unlink(tmp)
    return failures


if __name__ == "__main__":
    test_fire_log_workflow()
