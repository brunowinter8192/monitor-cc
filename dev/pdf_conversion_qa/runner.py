# INFRASTRUCTURE
import fcntl
import json
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psutil

from dev.pdf_conversion_qa.config import MINERU_LOCK_FILE
from dev.pdf_conversion_qa.memory_probe import kill_group, start_probe

LOCK_POLL_S = 5
PROBE_JOIN_TIMEOUT_S = 15
TEARDOWN_WAIT_S = 5.0


# FUNCTIONS
def run_monitored(
    cmd: list[str],
    env: dict,
    cwd: Path,
    log_path: Path,
    trace_path: Path,
    timeout_s: float,
    footprint_interval_s: float,
) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    load_avg_1m = os.getloadavg()[0]
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    with log_path.open("wb") as log:
        proc = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        pgid = os.getpgid(proc.pid)
        probe, stop_event, state = start_probe(proc.pid, pgid, trace_path, footprint_interval_s)
        timed_out = wait_with_timeout(proc, pgid, timeout_s)
        wall_s = time.monotonic() - t0
        kill_group(pgid)
        stop_event.set()
        probe.join(timeout=PROBE_JOIN_TIMEOUT_S)
    return {
        "started_at": started_at,
        "wall_s": round(wall_s, 2),
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "abort_reason": state["abort_reason"],
        "peak_footprint_gb": round(state["peak_footprint_gb"], 3),
        "min_available_gb": None if state["min_available_gb"] is None else round(state["min_available_gb"], 3),
        "start_available_gb": state["start_available_gb"],
        "probe_samples": state["samples"],
        "load_avg_1m_at_start": round(load_avg_1m, 2),
    }


def wait_with_timeout(proc: subprocess.Popen, pgid: int, timeout_s: float) -> bool:
    try:
        proc.wait(timeout=timeout_s)
        return False
    except subprocess.TimeoutExpired:
        kill_group(pgid)
        proc.wait()
        return True


@contextmanager
def mineru_lock(label: str):
    MINERU_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = open(MINERU_LOCK_FILE, "a")
    try:
        acquire_blocking(fd)
        sidecar = MINERU_LOCK_FILE.with_suffix(".lock")
        sidecar.write_text(json.dumps({
            "pid": os.getpid(),
            "command": "qa-measurement",
            "n_pdfs": 1,
            "pdfs": [label],
            "out_dir": "dev/pdf_conversion_qa/runs",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }))
        try:
            yield
        finally:
            sidecar.unlink(missing_ok=True)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def acquire_blocking(fd) -> None:
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            time.sleep(LOCK_POLL_S)


def fast_api_survivors() -> list[int]:
    return [p.pid for p in psutil.process_iter(["cmdline"]) if "mineru.cli.fast_api" in " ".join(p.info["cmdline"] or [])]


def teardown_fast_api() -> int:
    deadline = time.monotonic() + TEARDOWN_WAIT_S
    while time.monotonic() < deadline and fast_api_survivors():
        time.sleep(0.2)
    survivors = fast_api_survivors()
    for pid in survivors:
        try:
            psutil.Process(pid).kill()
        except psutil.NoSuchProcess:
            pass
    return len(survivors)
