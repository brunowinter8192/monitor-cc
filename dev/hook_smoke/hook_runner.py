# INFRASTRUCTURE
import os
import subprocess
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
