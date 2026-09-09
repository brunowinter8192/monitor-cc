# INFRASTRUCTURE
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .tmux_launcher import kill_session

_SESSION_PREFIX  = "monitor_cc_"
_MAX_AGE_SECONDS = 24 * 3600

# ORCHESTRATOR

def sweep_workflow(max_age_seconds: int = _MAX_AGE_SECONDS) -> list:
    sessions = list_monitor_sessions()
    results = sweep_sessions(sessions, max_age_seconds)
    return results

# FUNCTIONS

def list_monitor_sessions() -> list:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}|#{session_created}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    sessions = []
    for line in result.stdout.strip().split('\n'):
        if '|' not in line:
            continue
        name, created = line.split('|', 1)
        name, created = name.strip(), created.strip()
        if name.startswith(_SESSION_PREFIX) and created.isdigit():
            sessions.append((name, int(created)))
    return sessions

def sweep_sessions(sessions: list, max_age_seconds: int) -> list:
    now = time.time()
    return [sweep_one_session(name, created, now, max_age_seconds) for name, created in sessions]

def sweep_one_session(name: str, created: int, now: float, max_age_seconds: int) -> dict:
    age_seconds = now - created
    killed = age_seconds >= max_age_seconds
    if killed:
        kill_session(name)
    log_sweep_line(name, age_seconds, killed)
    return {"name": name, "age_seconds": age_seconds, "killed": killed}

def _resolve_monitor_cc_root() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent

def _log_path() -> Path:
    return _resolve_monitor_cc_root() / "src" / "logs" / "monitor_sweep.log"

def log_sweep_line(name: str, age_seconds: float, killed: bool) -> None:
    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    status = "KILLED" if killed else "SPARED"
    with log_path.open('a', encoding='utf-8') as f:
        f.write(f"{ts} {name} age={age_seconds / 3600:.1f}h {status}\n")

if __name__ == "__main__":
    sweep_workflow()
