# INFRASTRUCTURE
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRING_LOG_ENV = "MONITOR_CC_HOOK_FIRING_LOG"


# FUNCTIONS

def run_hook(hook: str, stdin_bytes: bytes, extra_env: dict = None, cwd=None) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory(prefix="hook_smoke_") as tmp:
        env = dict(os.environ)
        env[FIRING_LOG_ENV] = str(Path(tmp) / "hook_firing.jsonl")
        for key, value in (extra_env or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            ["python3", str(REPO_ROOT / hook)],
            input=stdin_bytes,
            capture_output=True,
            env=env,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
        )


def abort_if_failed(failures: list) -> None:
    if failures:
        print()
        print(f"FAILED: {len(failures)} case(s):")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
