"""Orchestrator: launch probe_a, probe_b, probe_c concurrently against target sessions.

Discovers the Opus main session dynamically (most recently active non-worker window).
Targets:
  - worker-Monitor_CC-ccwrap-phase1   (idle — completed Phase B)
  - worker-searxng-filter-cli          (idle — context limit)
  - <opus-main-session>                (working — active conversation)

Usage (from project root):
    ./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]
"""

# INFRASTRUCTURE
import argparse
import atexit
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROBE_BASE = Path(__file__).parent
REPORTS_DIR = PROBE_BASE / "01_reports"

WORKER_SESSIONS = [
    "worker-Monitor_CC-ccwrap-phase1",
    "worker-searxng-filter-cli",
]

_launched: list = []

# ORCHESTRATOR


def run_all_workflow():
    args = _parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    opus_session = _find_opus_session()
    if not opus_session:
        print("ERROR: no active Opus main session found", file=sys.stderr)
        sys.exit(1)

    sessions = WORKER_SESSIONS + [opus_session]
    print(f"[run_all] targets: {sessions}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    atexit.register(_terminate_all)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    _launch_probes(sessions, args.duration, ts)
    print(f"[run_all] all probes running ({args.duration}s). waiting…")
    for p in _launched:
        p.wait()

    print(f"[run_all] done. reports in {REPORTS_DIR}/")


# FUNCTIONS


def _parse_args():
    p = argparse.ArgumentParser(description="Run all three sensor probes concurrently")
    p.add_argument("--duration", type=int, default=120)
    return p.parse_args()


def _find_opus_session():
    """Return session name with the most recently active non-worker window."""
    r = subprocess.run(
        ["tmux", "list-windows", "-a", "-F", "#{session_name} #{window_index} #{window_activity}"],
        capture_output=True,
        text=True,
    )
    best_session, best_ts = None, 0
    for line in r.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 3:
            continue
        session, win_idx, wa_ts = parts
        if session.startswith("worker-"):
            continue
        # Only window 0 (CC conversation window); skip bead-tracker windows 3,4
        if win_idx not in ("0", "1", "2"):
            continue
        wa = int(wa_ts)
        if wa > best_ts:
            best_ts = wa
            best_session = session
    return best_session


def _launch_probes(sessions, duration, ts):
    for probe_script, outname in [
        ("probe_a.py", f"raw_probe_a_{ts}.csv"),
        ("probe_b.py", f"raw_probe_b_{ts}.csv"),
        ("probe_c.py", f"raw_probe_c_{ts}.csv"),
    ]:
        outfile = str(REPORTS_DIR / outname)
        cmd = [
            sys.executable,
            str(PROBE_BASE / probe_script),
            "--sessions", *sessions,
            "--duration", str(duration),
            "--outfile", outfile,
        ]
        p = subprocess.Popen(cmd)
        _launched.append(p)
        print(f"[run_all] {probe_script} → {outname} (pid={p.pid})")


def _terminate_all():
    for p in _launched:
        if p.poll() is None:
            p.terminate()


if __name__ == "__main__":
    run_all_workflow()
