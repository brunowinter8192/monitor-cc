"""Probe B: tmux pipe-pane byte-rate sensor.

For each session, activates pipe-pane on window 0's active pane, routing output
through byte_touch.py which touches an activity file and logs cumulative byte count.
Samples the activity file mtime and byte count every 1 second.

Usage:
    python3 probe_b.py --sessions S1 S2 S3 --duration 120 --outfile /path/to/out.csv

CSV columns: elapsed_sec, session, activity_mtime, bytecount_total, bytes_last_sec
Cleanup: deactivates pipe-pane on exit (atexit + signal handlers).
"""

# INFRASTRUCTURE
import argparse
import atexit
import csv
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BYTE_TOUCH = str(Path(__file__).parent / "byte_touch.py")
PYTHON3 = "/opt/homebrew/bin/python3"

# session → (activity_file, bytecount_file, pane_target)
_active_pipes: dict = {}

# ORCHESTRATOR


def probe_b_workflow():
    args = _parse_args()
    Path(args.outfile).parent.mkdir(parents=True, exist_ok=True)
    atexit.register(_cleanup_all)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    _setup_pipes(args.sessions)
    _run_probe(args.sessions, args.duration, args.outfile)
    print(f"[probe_b] done → {args.outfile}")


# FUNCTIONS


def _parse_args():
    p = argparse.ArgumentParser(description="Probe B: pipe-pane byte sensor")
    p.add_argument("--sessions", nargs="+", required=True)
    p.add_argument("--duration", type=int, default=120)
    p.add_argument("--outfile", required=True)
    return p.parse_args()


def _safe_name(session):
    return session.replace(":", "_").replace("/", "_")


def _get_active_pane(session):
    r = subprocess.run(
        ["tmux", "display-message", "-t", f"{session}:0", "-p", "#{pane_id}"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() or "0"


def _setup_pipes(sessions):
    for session in sessions:
        name = _safe_name(session)
        act_file = f"/tmp/probe-b-{name}.activity"
        cnt_file = f"/tmp/probe-b-{name}.bytecount"
        open(act_file, "a").close()
        with open(cnt_file, "w") as f:
            f.write("0\n")

        pane_id = _get_active_pane(session)
        pane_target = f"{session}:0"
        cmd = f"{PYTHON3} {BYTE_TOUCH} {act_file} {cnt_file}"
        subprocess.run(["tmux", "pipe-pane", "-t", pane_target, cmd], capture_output=True)
        _active_pipes[session] = (act_file, cnt_file, pane_target)
        print(f"[probe_b] pipe-pane active: {pane_target} (pane={pane_id})")


def _cleanup_all():
    for session, (act_file, cnt_file, pane_target) in list(_active_pipes.items()):
        subprocess.run(["tmux", "pipe-pane", "-t", pane_target], capture_output=True)
        for fpath in (act_file, cnt_file):
            if os.path.exists(fpath):
                os.unlink(fpath)
    _active_pipes.clear()
    print("[probe_b] cleanup done")


def _read_mtime(path):
    if not os.path.exists(path):
        return 0.0
    return os.stat(path).st_mtime


def _read_bytecount(path):
    if not os.path.exists(path):
        return 0
    raw = open(path).read().strip()
    return int(raw) if raw.isdigit() else 0


def _run_probe(sessions, duration, outfile):
    prev_bytes = {s: _read_bytecount(_active_pipes[s][1]) for s in sessions}

    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["elapsed_sec", "session", "activity_mtime", "bytecount_total", "bytes_last_sec"]
        )

        for t in range(duration):
            tick_start = time.monotonic()
            for session in sessions:
                act_file, cnt_file, _ = _active_pipes[session]
                mtime = _read_mtime(act_file)
                total = _read_bytecount(cnt_file)
                delta = max(0, total - prev_bytes[session])
                writer.writerow([t, session, f"{mtime:.3f}", total, delta])
                prev_bytes[session] = total
            f.flush()
            elapsed = time.monotonic() - tick_start
            remaining = 1.0 - elapsed
            if remaining > 0:
                time.sleep(remaining)


if __name__ == "__main__":
    probe_b_workflow()
