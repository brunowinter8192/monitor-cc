# INFRASTRUCTURE
import json
import shutil
import tempfile
from pathlib import Path

from hook_runner import FIRING_LOG_ENV, REPO_ROOT, abort_if_failed, run_hook

BLOCK_HOOK = "src/hooks/block_noop_edit.py"
REWRITE_HOOK = "src/hooks/rewrite_chained_sleep.py"
REWRITE_PAYLOAD = {
    "session_id": "test-sess-003",
    "tool_name": "Bash",
    "tool_input": {"command": "echo done && sleep 300"},
}


# ORCHESTRATOR

def test_fire_log_workflow() -> None:
    _test_block_fire()
    _test_rewrite_fire()
    _test_env_var_override()

    print()
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


def _test_block_fire() -> None:
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
        abort_if_failed(failures)
    elif rec is None:
        failures.append("block fire: no log line written")
        abort_if_failed(failures)
    else:
        if rec.get("decision") != "block":
            failures.append(f"block fire: expected decision=block, got {rec.get('decision')}")
            abort_if_failed(failures)
        if rec.get("hook") != "block_noop_edit":
            failures.append(f"block fire: expected hook=block_noop_edit, got {rec.get('hook')}")
            abort_if_failed(failures)
        if rec.get("tool") != "Edit":
            failures.append(f"block fire: expected tool=Edit, got {rec.get('tool')}")
            abort_if_failed(failures)
        if rec.get("session") != "test-sess-001":
            failures.append(f"block fire: expected session=test-sess-001, got {rec.get('session')}")
            abort_if_failed(failures)
        if "reason" not in rec:
            failures.append("block fire: missing 'reason' field")
            abort_if_failed(failures)
        if "rewritten" in rec:
            failures.append("block fire: unexpected 'rewritten' field on block record")
            abort_if_failed(failures)
        status = "OK  " if not [x for x in failures if "block fire" in x] else "FAIL"
        print(f"  [{status}] block fire: decision=block, hook=block_noop_edit, tool=Edit")


def _test_rewrite_fire() -> None:
    failures = []
    with tempfile.TemporaryDirectory(prefix="fire_log_rewrite_") as tmp:
        payload = dict(REWRITE_PAYLOAD, session_id="test-sess-002")
        exit_code, rec = _run_hook(REWRITE_HOOK, payload, Path(tmp) / "fire.jsonl")
    if exit_code != 0:
        failures.append(f"rewrite fire: expected exit 0, got {exit_code}")
        abort_if_failed(failures)
    elif rec is None:
        failures.append("rewrite fire: no log line written")
        abort_if_failed(failures)
    else:
        if rec.get("decision") != "rewrite":
            failures.append(f"rewrite fire: expected decision=rewrite, got {rec.get('decision')}")
            abort_if_failed(failures)
        if rec.get("hook") != "rewrite_chained_sleep":
            failures.append(f"rewrite fire: expected hook=rewrite_chained_sleep, got {rec.get('hook')}")
            abort_if_failed(failures)
        if rec.get("command") != "echo done && sleep 300":
            failures.append(f"rewrite fire: expected original command, got {rec.get('command')}")
            abort_if_failed(failures)
        if not rec.get("rewritten"):
            failures.append("rewrite fire: missing or empty 'rewritten' field")
            abort_if_failed(failures)
        if "reason" in rec:
            failures.append("rewrite fire: unexpected 'reason' field on rewrite record")
            abort_if_failed(failures)
        if rec.get("session") != "test-sess-002":
            failures.append(f"rewrite fire: expected session=test-sess-002, got {rec.get('session')}")
            abort_if_failed(failures)
        status = "OK  " if not [x for x in failures if "rewrite fire" in x] else "FAIL"
        print(f"  [{status}] rewrite fire: decision=rewrite, command+rewritten both present")


def _run_in_scratch_tree(tree_hooks: Path, log_env) -> int:
    result = run_hook(
        str(tree_hooks / "rewrite_chained_sleep.py"),
        json.dumps(REWRITE_PAYLOAD).encode(),
        extra_env={FIRING_LOG_ENV: log_env},
    )
    return result.returncode


def _test_env_var_override() -> None:
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
        abort_if_failed(failures)
    if written_to_canonical:
        failures.append("env-var override: unexpectedly written to canonical path")
        abort_if_failed(failures)
    if not control_hits_canonical:
        failures.append("env-var override: control run without the variable did not reach the canonical path")
        abort_if_failed(failures)
    status = "OK  " if not [x for x in failures if "env-var override" in x] else "FAIL"
    print(f"  [{status}] env-var override: log written to custom path, canonical untouched, control run reaches canonical")


if __name__ == "__main__":
    test_fire_log_workflow()
