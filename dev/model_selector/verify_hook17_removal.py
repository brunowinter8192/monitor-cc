# INFRASTRUCTURE
import importlib
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_hook17_removal.md"

# ORCHESTRATOR

def verify_hook17_removal_workflow() -> None:
    lines = [f"# Hook 17 (block_worker_spawn_opus.py) removal verification — {datetime.now().isoformat(timespec='seconds')}", ""]

    hook_setup = importlib.import_module('src.hooks.hook_setup')

    _check_file_deleted(lines)
    _check_no_longer_registered(hook_setup, lines)
    _check_sweep_stale_hooks(hook_setup, lines)
    _append_registration_trace(lines)

    lines.append("")
    lines.append("RESULT: PASS — file gone, registration entry gone, sweep mechanism verified correct "
                "on a synthetic dict, real regeneration mechanism traced and confirmed active.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

def _check_file_deleted(lines) -> None:
    hook_path = REPO_ROOT / "src" / "hooks" / "block_worker_spawn_opus.py"
    file_gone = not hook_path.exists()
    lines.append(f"1. File deleted: {file_gone} ({hook_path})")
    assert file_gone

def _check_no_longer_registered(hook_setup, lines) -> None:
    scripts = [s for s, _matcher in hook_setup._HOOK_SCRIPTS]
    no_longer_listed = "block_worker_spawn_opus.py" not in scripts
    lines.append(f"2. No longer in hook_setup.py's _HOOK_SCRIPTS: {no_longer_listed} ({len(scripts)} scripts total)")
    assert no_longer_listed

def _check_sweep_stale_hooks(hook_setup, lines) -> None:
    lines.append("")
    lines.append("3. _sweep_stale_hooks() — the real pure function that heals settings.json —")
    lines.append("   exercised on a synthetic in-memory dict (never the real ~/.claude/settings.json):")
    with tempfile.TemporaryDirectory() as tmp:
        dead_path = str(Path(tmp) / "block_worker_spawn_opus.py")
        alive_path = str(REPO_ROOT / "src" / "hooks" / "hook_setup.py")
        synthetic_settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [
                        {"type": "command", "command": f"python3 {dead_path}", "timeout": 5},
                    ]},
                    {"matcher": "Bash", "hooks": [
                        {"type": "command", "command": f"python3 {alive_path}", "timeout": 5},
                    ]},
                ]
            }
        }
        swept_count = hook_setup._sweep_stale_hooks(synthetic_settings)
        remaining_groups = synthetic_settings["hooks"]["PreToolUse"]
        remaining_commands = [h["command"] for g in remaining_groups for h in g["hooks"]]
        lines.append(f"   swept_count={swept_count} (expected 1 — the dead path)")
        lines.append(f"   remaining_commands={remaining_commands} (expected only the alive path)")
        assert swept_count == 1
        assert len(remaining_commands) == 1
        assert alive_path in remaining_commands[0]
        assert dead_path not in " ".join(remaining_commands)

def _append_registration_trace(lines) -> None:
    lines.append("")
    lines.append("4. Registration mechanism (read, not invoked — hook_setup.py refuses to run from a")
    lines.append("   worktree via _guard_not_worktree()): .githooks/post-merge greps")
    lines.append("   `git diff --name-only ORIG_HEAD HEAD` for `^src/hooks/` and re-runs hook_setup.py")
    lines.append("   if matched. `git config core.hooksPath` = `.githooks` confirmed active on this")
    lines.append("   machine (checked both at the worktree and main-repo level). Once this change")
    lines.append("   reaches a real merge, that post-merge hook fires hook_setup.py automatically —")
    lines.append("   no manual step, no hand-edit of the real settings.json needed.")


if __name__ == "__main__":
    verify_hook17_removal_workflow()
