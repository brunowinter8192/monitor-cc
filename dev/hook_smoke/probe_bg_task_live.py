# INFRASTRUCTURE
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from menubar import proc_cache

_REPORT_DIR = Path(__file__).parent / 'md'
_N_SESSIONS_FOR_COST_BENCH = 20


# ORCHESTRATOR

def snapshot_workflow(encoded_dir: str, session_id: str, task_id: str) -> None:
    tasks_dir = proc_cache._TASKS_BASE / encoded_dir / session_id / 'tasks'
    out_file = tasks_dir / f'{task_id}.output'
    size = out_file.stat().st_size if out_file.exists() else -1
    old = _old_predicate(tasks_dir)
    new = _new_predicate(encoded_dir, session_id)
    print(json.dumps({'size_bytes': size, 'old': old, 'new': new}))


def probe_bg_task_detection_workflow(encoded_dir: str, session_id: str, task_id: str, poll_secs: float, max_polls: int) -> None:
    real_run_rows = _poll_real_task(encoded_dir, session_id, task_id, poll_secs, max_polls)
    no_bg_row = _probe_no_bg_session(encoded_dir, session_id)
    synthetic_rows = _probe_synthetic_writer()
    cost = _bench_per_tick_cost()
    _write_report(real_run_rows, no_bg_row, synthetic_rows, cost)


# FUNCTIONS

def _old_predicate(tasks_dir: Path) -> bool:
    if not tasks_dir.exists():
        return False
    try:
        return any(f.stat().st_size == 0 for f in tasks_dir.glob('*.output') if f.is_file())
    except OSError:
        return False


def _new_predicate(encoded_dir: str, session_id: str) -> bool:
    proc_cache._bg_task_last_refresh = 0.0
    proc_cache._refresh_bg_task_cache(time.time())
    return proc_cache._has_active_bg(encoded_dir, session_id)


def _poll_real_task(encoded_dir: str, session_id: str, task_id: str, poll_secs: float, max_polls: int) -> list:
    tasks_dir = proc_cache._TASKS_BASE / encoded_dir / session_id / 'tasks'
    out_file = tasks_dir / f'{task_id}.output'
    rows = []
    t0 = time.time()
    for i in range(max_polls):
        size = out_file.stat().st_size if out_file.exists() else -1
        old = _old_predicate(tasks_dir)
        new = _new_predicate(encoded_dir, session_id)
        rows.append({'t_s': round(time.time() - t0, 1), 'size_bytes': size, 'old': old, 'new': new})
        print(f'  poll {i}: t={rows[-1]["t_s"]}s size={size}B old={old} new={new}')
        if size > 0:
            break
        time.sleep(poll_secs)
    for i in range(max_polls):
        size = out_file.stat().st_size if out_file.exists() else -1
        old = _old_predicate(tasks_dir)
        new = _new_predicate(encoded_dir, session_id)
        rows.append({'t_s': round(time.time() - t0, 1), 'size_bytes': size, 'old': old, 'new': new})
        print(f'  poll {i} (post-write): t={rows[-1]["t_s"]}s size={size}B old={old} new={new}')
        if new is False:
            break
        time.sleep(poll_secs)
    return rows


def _probe_no_bg_session(encoded_dir: str, session_id: str) -> dict:
    fake_session = 'no-such-session-id-control'
    tasks_dir = proc_cache._TASKS_BASE / encoded_dir / fake_session / 'tasks'
    old = _old_predicate(tasks_dir)
    new = _new_predicate(encoded_dir, fake_session)
    return {'old': old, 'new': new}


def _probe_synthetic_writer() -> list:
    scratch = proc_cache._TASKS_BASE / '__probe_synthetic__'
    tasks_dir = scratch / 'synthetic_sess' / 'tasks'
    tasks_dir.mkdir(parents=True, exist_ok=True)
    out_file = tasks_dir / 'fake_task.output'
    proc = subprocess.Popen(
        ['bash', '-c', f'exec > "{out_file}" 2>&1; for i in $(seq 1 10); do echo progress; sleep 2; done'],
        start_new_session=True)
    rows = []
    try:
        time.sleep(3)
        size = out_file.stat().st_size
        old = _old_predicate(tasks_dir)
        new = _new_predicate('__probe_synthetic__', 'synthetic_sess')
        rows.append({'phase': 'mid-flight', 'size_bytes': size, 'old': old, 'new': new})
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=5)
        time.sleep(0.5)
        size_after = out_file.stat().st_size
        old_after = _old_predicate(tasks_dir)
        new_after = _new_predicate('__probe_synthetic__', 'synthetic_sess')
        rows.append({'phase': 'after-kill', 'size_bytes': size_after, 'old': old_after, 'new': new_after})
    finally:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        shutil.rmtree(scratch, ignore_errors=True)
    return rows


def _bench_per_tick_cost() -> dict:
    session_ids = [f'bench-session-{i}' for i in range(_N_SESSIONS_FOR_COST_BENCH)]
    encoded_dir = 'bench-encoded-dir'

    proc_cache._bg_task_last_refresh = 0.0
    t0 = time.time()
    proc_cache._refresh_bg_task_cache(time.time())
    refresh_ms = (time.time() - t0) * 1000

    t0 = time.time()
    for sid in session_ids:
        proc_cache._has_active_bg(encoded_dir, sid)
    hit_ms = (time.time() - t0) * 1000

    return {
        'n_sessions': _N_SESSIONS_FOR_COST_BENCH,
        'refresh_tick_ms': round(refresh_ms, 2),
        'cache_hit_tick_ms_for_n_sessions': round(hit_ms, 3),
        'refresh_interval_s': proc_cache._PROC_REFRESH_INTERVAL,
    }


def _write_report(real_run_rows: list, no_bg_row: dict, synthetic_rows: list, cost: dict) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out_path = _REPORT_DIR / f'{ts}_bg_task_detection_probe.md'

    mid_flight = next((r for r in real_run_rows if r['size_bytes'] > 0), None)
    completed = real_run_rows[-1] if real_run_rows else None
    synth_mid = next((r for r in synthetic_rows if r['phase'] == 'mid-flight'), None)

    lines = []
    lines.append('# Background-task detection probe — real rag-cli index run + synthetic writer\n')
    lines.append(f'Run: {datetime.now(timezone.utc).isoformat()}\n')
    lines.append('## Required comparison table\n')
    lines.append('| case | old 0-byte predicate | new handle predicate |')
    lines.append('|---|---|---|')
    if mid_flight:
        lines.append(f"| real rag-cli index, mid-flight, output non-empty ({mid_flight['size_bytes']}B) | {mid_flight['old']} | {mid_flight['new']} |")
    if completed:
        lines.append(f"| same run, after completion ({completed['size_bytes']}B) | {completed['old']} | {completed['new']} |")
    lines.append(f"| session with no background task at all | {no_bg_row['old']} | {no_bg_row['new']} |")
    if synth_mid:
        lines.append(f"| synthetic writing loop, >0 bytes, still running ({synth_mid['size_bytes']}B) | {synth_mid['old']} | {synth_mid['new']} |")
    lines.append('')
    lines.append('## Raw poll trail — real rag-cli index task\n')
    lines.append('| t (s) | size (bytes) | old | new |')
    lines.append('|---|---|---|---|')
    for r in real_run_rows:
        lines.append(f"| {r['t_s']} | {r['size_bytes']} | {r['old']} | {r['new']} |")
    lines.append('')
    lines.append('## Synthetic writer round-trip\n')
    lines.append('| phase | size (bytes) | old | new |')
    lines.append('|---|---|---|---|')
    for r in synthetic_rows:
        lines.append(f"| {r['phase']} | {r['size_bytes']} | {r['old']} | {r['new']} |")
    lines.append('')
    lines.append('## Per-tick cost (batched lsof scan, TTL-cached)\n')
    lines.append(f"- Refresh tick (1 global `lsof +D` scan, TTL expired): **{cost['refresh_tick_ms']} ms**")
    lines.append(f"- Cache-hit tick ({cost['n_sessions']} sessions, `_has_active_bg` string-match only, no subprocess): **{cost['cache_hit_tick_ms_for_n_sessions']} ms**")
    lines.append(f"- TTL: {cost['refresh_interval_s']}s (shared with `_refresh_cc_proc_cache`) — the refresh cost is paid once per TTL window, not once per session per tick.")
    lines.append('')
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'\nReport written: {out_path}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--encoded-dir', required=True)
    ap.add_argument('--session-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--poll-secs', type=float, default=3.0)
    ap.add_argument('--max-polls', type=int, default=100)
    ap.add_argument('--snapshot', action='store_true',
                     help='print one measurement and exit (safe for same-session use in a caller-driven loop)')
    args = ap.parse_args()
    if args.snapshot:
        snapshot_workflow(args.encoded_dir, args.session_id, args.task_id)
    else:
        probe_bg_task_detection_workflow(args.encoded_dir, args.session_id, args.task_id, args.poll_secs, args.max_polls)
