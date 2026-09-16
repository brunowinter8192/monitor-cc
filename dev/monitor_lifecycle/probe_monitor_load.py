# INFRASTRUCTURE
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

_SESSION_PREFIX = "monitor_cc_"
_REPORT_DIR     = Path(__file__).resolve().parent / "reports"
_MODE_RE = re.compile(r'--mode\s+(\S+)')

# ORCHESTRATOR

def probe_monitor_load_workflow() -> None:
    rows = collect_pane_rows()
    rows.sort(key=lambda r: r['cpu_seconds'], reverse=True)
    print_table(rows)
    write_report(rows)

# FUNCTIONS

def collect_pane_rows() -> list:
    now = time.time()
    panes = list_monitor_panes()
    rows = []
    for pane in panes:
        stats = ps_stats(pane['pid'])
        rows.append({
            'session': pane['session'],
            'session_age_h': (now - pane['session_created']) / 3600,
            'mode': pane['mode'],
            'pid': pane['pid'],
            'pane_etime': stats['etime'],
            'cpu_time': stats['cputime'],
            'cpu_seconds': stats['cpu_seconds'],
            'pct_cpu': stats['pct_cpu'],
        })
    return rows

def list_monitor_panes() -> list:
    result = subprocess.run(
        ["tmux", "list-panes", "-a", "-F",
         "#{session_name}|#{session_created}|#{pane_index}|#{pane_pid}|#{pane_start_command}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    panes = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split('|', 4)
        if len(parts) != 5:
            continue
        session, created, pane_idx, pid, start_cmd = parts
        if not session.startswith(_SESSION_PREFIX):
            continue
        m = _MODE_RE.search(start_cmd)
        panes.append({
            'session': session,
            'session_created': int(created) if created.isdigit() else 0,
            'pane_idx': pane_idx,
            'pid': int(pid) if pid.isdigit() else -1,
            'mode': m.group(1) if m else '?',
        })
    return panes

def ps_stats(pid: int) -> dict:
    result = subprocess.run(
        ["ps", "-o", "etime=,cputime=,%cpu=", "-p", str(pid)],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {'etime': '-', 'cputime': '-', 'cpu_seconds': -1.0, 'pct_cpu': '-'}
    fields = result.stdout.split()
    etime, cputime, pct_cpu = fields[0], fields[1], fields[2]
    return {
        'etime': etime,
        'cputime': cputime,
        'cpu_seconds': parse_clock(cputime),
        'pct_cpu': pct_cpu,
    }

def parse_clock(value: str) -> float:
    days = 0
    if '-' in value:
        day_part, value = value.split('-', 1)
        days = int(day_part)
    parts = [float(p) for p in value.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def print_table(rows: list) -> None:
    header = f"{'SESSION':<20} {'SESSION_AGE':>11} {'MODE':<13} {'PID':>8} {'PANE_AGE':>10} {'CPU_TIME':>10} {'%CPU':>6}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['session']:<20} {r['session_age_h']:>10.1f}h {r['mode']:<13} {r['pid']:>8} "
            f"{r['pane_etime']:>10} {r['cpu_time']:>10} {r['pct_cpu']:>6}"
        )
    print(f"\n{len(rows)} pane(s) across monitor_cc_* sessions.")

def write_report(rows: list) -> Path:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    out_path = _REPORT_DIR / f"{ts.strftime('%Y-%m-%d')}_monitor_load_baseline.md"
    lines = [
        "# Monitor pane load baseline",
        "",
        f"Run: {ts.isoformat()}",
        f"Panes: {len(rows)} across monitor_cc_* sessions (sorted by CPU time, descending)",
        "",
        "| session | session_age | mode | pid | pane_age | cpu_time | %cpu |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['session']} | {r['session_age_h']:.1f}h | {r['mode']} | {r['pid']} | "
            f"{r['pane_etime']} | {r['cpu_time']} | {r['pct_cpu']} |"
        )
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written: {out_path}")
    return out_path


if __name__ == "__main__":
    probe_monitor_load_workflow()
