# INFRASTRUCTURE
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from src.monitor_root import resolve_monitor_cc_root
from src.tmux_launcher import kill_session

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
        _append_log_line(f"NOSESSIONS rc={result.returncode}")
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

def _append_log_line(text: str) -> None:
    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with log_path.open('a', encoding='utf-8') as f:
        f.write(f"{ts} {text}\n")

def _log_path() -> Path:
    return _resolve_monitor_cc_root() / "src" / "logs" / "monitor_sweep.log"

def _resolve_monitor_cc_root() -> Path:
    return resolve_monitor_cc_root(_report_root)

def _report_root(root: Path, source: str) -> None:
    log_path = root / "src" / "logs" / "monitor_sweep.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with log_path.open('a', encoding='utf-8') as f:
        f.write(f"{ts} ROOT source={source} root={root}\n")

def sweep_sessions(sessions: list, max_age_seconds: int) -> list:
    now = time.time()
    return [sweep_one_session(name, created, now, max_age_seconds) for name, created in sessions]

def sweep_one_session(name: str, created: int, now: float, max_age_seconds: int) -> dict:
    age_seconds = now - created
    expired = age_seconds >= max_age_seconds
    killed = kill_session(name) if expired else False
    status = "KILLED" if killed else ("KILL_FAILED" if expired else "SPARED")
    log_sweep_line(name, age_seconds, status)
    return {"name": name, "age_seconds": age_seconds, "killed": killed}

def log_sweep_line(name: str, age_seconds: float, status: str) -> None:
    _append_log_line(f"{name} age={age_seconds / 3600:.1f}h {status}")

if __name__ == "__main__":
    sweep_workflow()
