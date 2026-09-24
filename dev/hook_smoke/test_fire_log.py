# INFRASTRUCTURE
import json
import shutil
import sys
import tempfile
from pathlib import Path

from hook_runner import FIRING_LOG_ENV, REPO_ROOT, run_hook

BLOCK_HOOK = "src/hooks/block_noop_edit.py"
REWRITE_HOOK = "src/hooks/rewrite_chained_sleep.py"
REWRITE_PAYLOAD = {
    "session_id": "test-sess-003",
    "tool_name": "Bash",
    "tool_input": {"command": "echo done && sleep 300"},
}


# ORCHESTRATOR

def test_fire_log_workflow() -> None:
    failures = []

    failures.extend(_test_block_fire())
    failures.extend(_test_rewrite_fire())
    failures.extend(_test_env_var_override())

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All fire-log tests passed.")


# FUNCTIONS

def _last_record(log_path: Path):
    if not log_path.exists():
        return None
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def _run_hook(hook: str, payload: dict, log_path: Path) -> tuple:
    result = run_hook(hook, json.dumps(payload).encode(), extra_env={FIRING_LOG_ENV: str(log_path)})
    return result.returncode, _last_record(log_path)


def _test_block_fire() -> list:
    failures = []
    with tempfile.TemporaryDirectory(prefix="fire_log_block_") as tmp:
        payload = {
            "session_id": "test-sess-001",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/test.py",
                "old_string": "same content",
                "new_string": "same content",
            },
        }
        exit_code, rec = _run_hook(BLOCK_HOOK, payload, Path(tmp) / "fire.jsonl")
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
    return failures


def _test_rewrite_fire() -> list:
    failures = []
    with tempfile.TemporaryDirectory(prefix="fire_log_rewrite_") as tmp:
        payload = dict(REWRITE_PAYLOAD, session_id="test-sess-002")
        exit_code, rec = _run_hook(REWRITE_HOOK, payload, Path(tmp) / "fire.jsonl")
    if exit_code != 0:
        failures.append(f"rewrite fire: expected exit 0, got {exit_code}")
    elif rec is None:
        failures.append("rewrite fire: no log line written")
    else:
        if rec.get("decision") != "rewrite":
            failures.append(f"rewrite fire: expected decision=rewrite, got {rec.get('decision')}")
        if rec.get("hook") != "rewrite_chained_sleep":
            failures.append(f"rewrite fire: expected hook=rewrite_chained_sleep, got {rec.get('hook')}")
        if rec.get("command") != "echo done && sleep 300":
            failures.append(f"rewrite fire: expected original command, got {rec.get('command')}")
        if not rec.get("rewritten"):
            failures.append("rewrite fire: missing or empty 'rewritten' field")
        if "reason" in rec:
            failures.append("rewrite fire: unexpected 'reason' field on rewrite record")
        if rec.get("session") != "test-sess-002":
            failures.append(f"rewrite fire: expected session=test-sess-002, got {rec.get('session')}")
        status = "OK  " if not [x for x in failures if "rewrite fire" in x] else "FAIL"
        print(f"  [{status}] rewrite fire: decision=rewrite, command+rewritten both present")
    return failures


def _run_in_scratch_tree(tree_hooks: Path, log_env) -> int:
    result = run_hook(
        str(tree_hooks / "rewrite_chained_sleep.py"),
        json.dumps(REWRITE_PAYLOAD).encode(),
        extra_env={FIRING_LOG_ENV: log_env},
    )
    return result.returncode


def _test_env_var_override() -> list:
    failures = []
    with tempfile.TemporaryDirectory(prefix="fire_log_override_") as tmp:
        scratch = Path(tmp)
        tree_hooks = scratch / "src" / "hooks"
        shutil.copytree(REPO_ROOT / "src" / "hooks", tree_hooks)
        canonical = scratch / "src" / "logs" / "hook_firing.jsonl"
        canonical.parent.mkdir()
        custom = scratch / "custom.jsonl"

        _run_in_scratch_tree(tree_hooks, str(custom))
        written_to_custom = custom.exists() and custom.stat().st_size > 0
        written_to_canonical = canonical.exists() and canonical.stat().st_size > 0

        _run_in_scratch_tree(tree_hooks, None)
        control_hits_canonical = canonical.exists() and canonical.stat().st_size > 0

    if not written_to_custom:
        failures.append("env-var override: nothing written to custom path")
    if written_to_canonical:
        failures.append("env-var override: unexpectedly written to canonical path")
    if not control_hits_canonical:
        failures.append("env-var override: control run without the variable did not reach the canonical path")
    status = "OK  " if not [x for x in failures if "env-var override" in x] else "FAIL"
    print(f"  [{status}] env-var override: log written to custom path, canonical untouched, control run reaches canonical")
    return failures


if __name__ == "__main__":
    test_fire_log_workflow()
