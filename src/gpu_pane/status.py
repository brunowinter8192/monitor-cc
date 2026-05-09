# INFRASTRUCTURE
import json
import os
import pathlib
import subprocess
import urllib.request
import urllib.error

SERVERS = ['embedding', 'reranker', 'splade']
LOCK_DIR = pathlib.Path.home() / ".rag-locks"

# ORCHESTRATOR

# Return status dicts for all three GPU servers
def all_statuses() -> list[dict]:
    return [server_status(n) for n in SERVERS]

# FUNCTIONS

# Read port file, probe health, read RSS; skip HTTP if stopped
def server_status(name: str) -> dict:
    port_file = LOCK_DIR / f"rag-server-{name}.port"
    try:
        data = json.loads(port_file.read_text())
        port = data.get("port")
        pid = data.get("pid")
    except (FileNotFoundError, json.JSONDecodeError):
        return _stopped(name)

    try:
        os.kill(pid, 0)
    except (ProcessLookupError, TypeError):
        port_file.unlink(missing_ok=True)
        return _stopped(name)

    healthy = _check_health(port)
    rss_mb = _read_rss_mb(pid)
    return {"name": name, "status": "running", "port": port, "pid": pid,
            "rss_mb": rss_mb, "healthy": healthy}


# Return stopped-state dict
def _stopped(name: str) -> dict:
    return {"name": name, "status": "stopped", "port": None, "pid": None,
            "rss_mb": None, "healthy": False}


# GET /health on port; return True if 200, False on any error
def _check_health(port: int) -> bool:
    try:
        req = urllib.request.Request(f'http://localhost:{port}/health')
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


# Return RSS in MB via `ps -o rss=`; None on failure
def _read_rss_mb(pid: int) -> int | None:
    try:
        r = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return round(int(r.stdout.strip()) / 1024)
    except Exception:
        pass
    return None
