# INFRASTRUCTURE
import argparse
import csv
import signal
import subprocess
import sys
import time
from pathlib import Path


# ORCHESTRATOR

def probe_a_workflow():
    args = _parse_args()
    Path(args.outfile).parent.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    _run_probe(args.sessions, args.duration, args.outfile)
    print(f"[probe_a] done → {args.outfile}")


# FUNCTIONS

def _parse_args():
    p = argparse.ArgumentParser(description="Probe A: window_activity polling")
    p.add_argument("--sessions", nargs="+", required=True)
    p.add_argument("--duration", type=int, default=120)
    p.add_argument("--outfile", required=True)
    return p.parse_args()


def _run_probe(sessions, duration, outfile):
    prev = {}
    for s in sessions:
        prev[s] = _get_window_activity(s)

    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["elapsed_sec", "session", "window_activity_ts", "delta"])

        for t in range(duration):
            tick_start = time.monotonic()
            for session in sessions:
                wa = _get_window_activity(session)
                delta = 1 if wa != prev[session] else 0
                writer.writerow([t, session, wa, delta])
                prev[session] = wa
            f.flush()
            elapsed = time.monotonic() - tick_start
            remaining = 1.0 - elapsed
            if remaining > 0:
                time.sleep(remaining)


def _get_window_activity(session):
    r = subprocess.run(
        ["tmux", "display-message", "-t", f"{session}:0", "-p", "#{window_activity}"],
        capture_output=True,
        text=True,
    )
    val = r.stdout.strip()
    return int(val) if val.isdigit() else 0


if __name__ == "__main__":
    probe_a_workflow()
