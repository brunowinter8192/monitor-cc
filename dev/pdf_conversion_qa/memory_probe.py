# INFRASTRUCTURE
import json
import os
import re
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil

from dev.pdf_conversion_qa.config import (
    FOOTPRINT_TIMEOUT_S,
    WATCHDOG_FLOOR_GB,
    WATCHDOG_PROC_GB,
)

UNIT_TO_BYTES = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
PHYS_RE = re.compile(r"phys_footprint:\s+([\d.]+)\s*(B|KB|MB|GB)")
FOOTPRINT_WORKERS = 8


# FUNCTIONS
def start_probe(
    root_pid: int,
    pgid: int,
    trace_path: Path,
    sample_interval_s: float,
    footprint_interval_s: float,
) -> tuple[threading.Thread, threading.Event, dict]:
    stop_event = threading.Event()
    state = {
        "peak_footprint_gb": 0.0,
        "min_available_gb": None,
        "start_available_gb": round(psutil.virtual_memory().available / 2 ** 30, 3),
        "abort_reason": None,
        "samples": 0,
    }
    thread = threading.Thread(
        target=probe_loop,
        args=(root_pid, pgid, trace_path, sample_interval_s, footprint_interval_s, stop_event, state),
        daemon=True,
        name="memory_probe",
    )
    thread.start()
    return thread, stop_event, state


def probe_loop(
    root_pid: int,
    pgid: int,
    trace_path: Path,
    sample_interval_s: float,
    footprint_interval_s: float,
    stop_event: threading.Event,
    state: dict,
) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    last_footprint_t = 0.0
    tree_gb: Optional[float] = None
    with trace_path.open("a") as trace:
        while True:
            available_gb = psutil.virtual_memory().available / 2 ** 30
            now = time.monotonic()
            if now - last_footprint_t >= footprint_interval_s:
                sampled = sample_tree_footprint_gb(root_pid)
                if sampled is not None:
                    tree_gb = sampled
                last_footprint_t = now
            record_sample(state, trace, available_gb, tree_gb)
            reason = guard_reason(available_gb, tree_gb)
            if reason is not None:
                state["abort_reason"] = reason
                kill_group(pgid)
                return
            if stop_event.wait(sample_interval_s):
                return


def record_sample(state: dict, trace, available_gb: float, tree_gb: Optional[float]) -> None:
    state["samples"] += 1
    if tree_gb is not None:
        state["peak_footprint_gb"] = max(state["peak_footprint_gb"], tree_gb)
    previous_min = state["min_available_gb"]
    state["min_available_gb"] = available_gb if previous_min is None else min(previous_min, available_gb)
    trace.write(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "available_gb": round(available_gb, 3),
        "tree_footprint_gb": None if tree_gb is None else round(tree_gb, 3),
    }) + "\n")
    trace.flush()


def guard_reason(available_gb: float, tree_gb: Optional[float]) -> Optional[str]:
    if available_gb < WATCHDOG_FLOOR_GB:
        return f"system available {available_gb:.2f} GB < {WATCHDOG_FLOOR_GB} GB"
    if tree_gb is not None and tree_gb > WATCHDOG_PROC_GB:
        return f"tree footprint {tree_gb:.2f} GB > {WATCHDOG_PROC_GB} GB"
    return None


def kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def sample_tree_footprint_gb(root_pid: int) -> Optional[float]:
    pids = tree_pids(root_pid)
    if not pids:
        return None
    with ThreadPoolExecutor(max_workers=FOOTPRINT_WORKERS) as pool:
        values = list(pool.map(footprint_gb, pids))
    found = [value for value in values if value is not None]
    return sum(found) if found else None


def tree_pids(root_pid: int) -> list[int]:
    try:
        root = psutil.Process(root_pid)
        return [root.pid] + [child.pid for child in root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return []


def footprint_gb(pid: int) -> Optional[float]:
    try:
        result = subprocess.run(
            ["/usr/bin/footprint", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=FOOTPRINT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("phys_footprint:"):
            match = PHYS_RE.search(stripped)
            if match:
                return float(match.group(1)) * UNIT_TO_BYTES[match.group(2)] / 2 ** 30
            return None
    return None
