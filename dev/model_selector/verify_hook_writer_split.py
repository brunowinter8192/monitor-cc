# INFRASTRUCTURE
import importlib
import io
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_hook_writer_split.md"

# ORCHESTRATOR

def verify_hook_writer_split_workflow() -> None:
    lines = [f"# hook_writer.py split verification — {datetime.now().isoformat(timespec='seconds')}", ""]
    with tempfile.TemporaryDirectory() as tmp:
        hook_writer = _load_hook_writer_with_tmp_app_support(Path(tmp))
        session_id = "test-session-model-selector"
        cwd = "/tmp/test-cwd"

        _run_payload(hook_writer, {"hook_event_name": "UserPromptSubmit", "session_id": session_id, "cwd": cwd})
        state_after_prompt = json.loads(hook_writer._HOOK_STATE_FILE.read_text())
        lines.append(f"UserPromptSubmit -> hooks.json: {state_after_prompt}")
        assert state_after_prompt[session_id]["status"] == "working"

        _run_payload(hook_writer, {"hook_event_name": "Stop", "session_id": session_id, "cwd": cwd})
        state_after_stop = json.loads(hook_writer._HOOK_STATE_FILE.read_text())
        lines.append(f"Stop -> hooks.json: {state_after_stop}")
        assert state_after_stop[session_id]["status"] == "idle"

        queue_file_exists = (Path(tmp) / "msg_queue.json").exists()
        queue_lock_exists = (Path(tmp) / "queue.lock").exists()
        lines.append(f"msg_queue.json created: {queue_file_exists} (expected False)")
        lines.append(f"queue.lock created: {queue_lock_exists} (expected False)")
        assert not queue_file_exists
        assert not queue_lock_exists

        lines.append("")
        lines.append("RESULT: PASS — hook-state half intact, no queue side effects.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

# FUNCTIONS

def _load_hook_writer_with_tmp_app_support(tmp_dir: Path):
    spec_path = REPO_ROOT / "src" / "menubar" / "hook_writer.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_writer_under_test", spec_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._APP_SUPPORT     = tmp_dir
    module._HOOK_STATE_FILE = tmp_dir / "hooks.json"
    module._HOOK_LOCK_FILE  = tmp_dir / "hooks.lock"
    return module

def _run_payload(hook_writer, payload: dict) -> None:
    real_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        hook_writer.hook_writer_workflow()
    finally:
        sys.stdin = real_stdin


if __name__ == "__main__":
    verify_hook_writer_split_workflow()
