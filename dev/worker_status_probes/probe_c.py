"""Probe C: tmux -C control-mode event stream.

Spawns `tmux -C attach-session -t <session>` per target session. A reader thread
parses %output and %extended-output events, filtering to panes in window 0 only
(avoids bead-tracker noise from windows 3/4 of multi-window sessions). Counters
(events, bytes) are sampled and reset every 1 second.

Usage:
    python3 probe_c.py --sessions S1 S2 S3 --duration 120 --outfile /path/to/out.csv

CSV columns: elapsed_sec, session, events_last_sec, bytes_last_sec
Cleanup: sends detach-client to each subprocess stdin, then kills.

Protocol reference: vonbai/goalx cli/tmux_control_watcher.go
                    Handfish/Geppetto docs/WATCHER_ACTIVITY_DETECTION.md
"""

# INFRASTRUCTURE
import argparse
import atexit
import csv
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# session → subprocess
_procs: dict = {}

# ORCHESTRATOR


def probe_c_workflow():
    args = _parse_args()
    Path(args.outfile).parent.mkdir(parents=True, exist_ok=True)
    atexit.register(_cleanup_all)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    _run_probe(args.sessions, args.duration, args.outfile)
    print(f"[probe_c] done → {args.outfile}")


# FUNCTIONS


def _parse_args():
    p = argparse.ArgumentParser(description="Probe C: tmux control-mode event stream")
    p.add_argument("--sessions", nargs="+", required=True)
    p.add_argument("--duration", type=int, default=120)
    p.add_argument("--outfile", required=True)
    return p.parse_args()


def _get_window0_pane_ids(session):
    r = subprocess.run(
        ["tmux", "list-panes", "-t", f"{session}:0", "-F", "#{pane_id}"],
        capture_output=True,
        text=True,
    )
    return set(r.stdout.split())


def _start_control_client(session):
    proc = subprocess.Popen(
        ["tmux", "-C", "attach-session", "-t", session],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    _procs[session] = proc
    return proc


def _stop_control_client(session):
    proc = _procs.get(session)
    if proc is None:
        return
    if proc.poll() is None:
        proc.stdin.write(b"detach-client\n")
        proc.stdin.flush()
        proc.stdin.close()
        proc.wait(timeout=3)
    if proc.poll() is None:
        proc.kill()
        proc.wait()


def _cleanup_all():
    for session in list(_procs):
        _stop_control_client(session)
    _procs.clear()
    print("[probe_c] cleanup done")


def _reader_thread(proc, pane_ids, session, counters, lock, stop_event):
    """Read %output / %extended-output lines and update per-second counters."""
    for raw in proc.stdout:
        if stop_event.is_set():
            break
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        pane_id, payload = _parse_output_event(line)
        if pane_id is None:
            continue
        if pane_ids and pane_id not in pane_ids:
            continue
        with lock:
            counters[session]["events"] += 1
            counters[session]["bytes"] += len(payload)


def _parse_output_event(line):
    """Return (pane_id, payload) for %output and %extended-output lines, else (None, None)."""
    if line.startswith("%output "):
        rest = line[len("%output "):]
        parts = rest.split(" ", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    elif line.startswith("%extended-output "):
        rest = line[len("%extended-output "):]
        parts = rest.split(" ", 2)
        if len(parts) == 3:
            payload = parts[2]
            if payload.startswith(": "):
                payload = payload[2:]
            return parts[0], payload
    return None, None


def _run_probe(sessions, duration, outfile):
    lock = threading.Lock()
    counters = {s: {"events": 0, "bytes": 0} for s in sessions}
    stop_event = threading.Event()
    threads = []

    for session in sessions:
        pane_ids = _get_window0_pane_ids(session)
        proc = _start_control_client(session)
        t = threading.Thread(
            target=_reader_thread,
            args=(proc, pane_ids, session, counters, lock, stop_event),
            daemon=True,
        )
        t.start()
        threads.append(t)
        print(f"[probe_c] control client for {session} (panes={pane_ids})")

    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["elapsed_sec", "session", "events_last_sec", "bytes_last_sec"])

        for t in range(duration):
            tick_start = time.monotonic()
            time.sleep(1.0)
            with lock:
                for session in sessions:
                    ev = counters[session]["events"]
                    by = counters[session]["bytes"]
                    counters[session] = {"events": 0, "bytes": 0}
                    writer.writerow([t, session, ev, by])
            f.flush()

    stop_event.set()
    _cleanup_all()


if __name__ == "__main__":
    probe_c_workflow()
