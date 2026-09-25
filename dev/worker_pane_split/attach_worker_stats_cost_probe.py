# INFRASTRUCTURE
import importlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_worker_tmux = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tmux')

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
N_WORKERS_TYPICAL = 5
POLL_INTERVAL = 0.5


# ORCHESTRATOR

def run_probe_workflow():
    all_worktree_files = _find_worktree_jsonls(limit=0)
    lines = _build_report(all_worktree_files)
    _write_report(lines)


# FUNCTIONS

def _find_worktree_jsonls(limit: int) -> list:
    if not PROJECTS_DIR.exists():
        return []
    candidates = []
    for d in PROJECTS_DIR.iterdir():
        if not d.is_dir() or '--claude-worktrees-' not in d.name:
            continue
        for f in d.glob('*.jsonl'):
            if f.name.startswith('agent-'):
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            candidates.append((size, f))
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[:limit] if limit else candidates


def _build_report(all_worktree_files: list) -> list:
    lines = _report_header()
    if not all_worktree_files:
        lines += _no_files_found_lines()
        return lines
    lines += _files_found_lines(all_worktree_files)

    typical_set, typical_paths = _select_typical_set(all_worktree_files)
    lines += _typical_set_lines(typical_set)

    result_typical = _time_cold_then_warm(typical_paths)
    cold_typical = result_typical['cold_s']
    warm_typical = result_typical['warm_s']
    lines += _cold_warm_summary_lines(cold_typical, warm_typical)
    lines += _extrapolation_lines(cold_typical, warm_typical)

    lines += _stress_test_lines(all_worktree_files)
    return lines


def _report_header() -> list:
    lines = []
    lines.append("# attach_worker_stats real-file cost measurement")
    lines.append("")
    lines.append(f"Run: {datetime.now().isoformat()}")
    lines.append("")
    return lines


def _no_files_found_lines() -> list:
    msg = "No real worker-worktree JSONL files found under ~/.claude/projects/ -- cannot measure."
    print(msg)
    return [msg]


def _files_found_lines(all_worktree_files: list) -> list:
    print(f"Found {len(all_worktree_files)} real worker-worktree JSONL files.")
    return [
        f"Found {len(all_worktree_files)} real worker-worktree JSONL files under "
        f"`~/.claude/projects/*--claude-worktrees-*/`.",
        "",
    ]


def _select_typical_set(all_worktree_files: list) -> tuple:
    sizes_sorted = sorted(all_worktree_files, key=lambda t: t[0])
    mid = len(sizes_sorted) // 2
    start = max(0, mid - N_WORKERS_TYPICAL // 2)
    typical_set = sizes_sorted[start:start + N_WORKERS_TYPICAL]
    typical_paths = [p for _, p in typical_set]
    return typical_set, typical_paths


def _typical_set_lines(typical_set: list) -> list:
    lines = []
    lines.append("## Typical set (5 workers, median-sized real files)")
    lines.append("")
    lines.append("| File | Size (MB) |")
    lines.append("|---|---|")
    for size, p in typical_set:
        lines.append(f"| `{p.name}` | {size / 1_048_576:.2f} |")
    total_typical_mb = sum(s for s, _ in typical_set) / 1_048_576
    lines.append("")
    lines.append(f"Total bytes across the 5 files: {total_typical_mb:.2f} MB")
    print(f"Typical 5-worker set: {total_typical_mb:.2f} MB total")
    return lines


def _time_cold_then_warm(paths: list) -> dict:
    workers, path_by_session = _fake_workers_for_paths(paths)
    orig_find = mod_worker_tmux.find_worker_jsonl
    mod_worker_tmux.find_worker_jsonl = lambda session: path_by_session.get(session)
    try:
        cache: dict = {}
        t0 = time.perf_counter()
        mod_worker_tmux.attach_worker_stats(workers, cache)
        cold_elapsed = time.perf_counter() - t0

        t1 = time.perf_counter()
        mod_worker_tmux.attach_worker_stats(workers, cache)
        warm_elapsed = time.perf_counter() - t1
    finally:
        mod_worker_tmux.find_worker_jsonl = orig_find
    return {'cold_s': cold_elapsed, 'warm_s': warm_elapsed, 'workers': workers}


def _fake_workers_for_paths(paths: list) -> tuple:
    workers = [{'name': f'w{i}', 'session': f'sess-{i}'} for i in range(len(paths))]
    path_by_session = {w['session']: p for w, p in zip(workers, paths)}
    return workers, path_by_session


def _cold_warm_summary_lines(cold_typical: float, warm_typical: float) -> list:
    print(f"attach_worker_stats COLD (fresh cache) over 5 typical workers: {cold_typical*1000:.1f} ms")
    print(f"attach_worker_stats WARM (cached, no new bytes) over the same 5 workers: {warm_typical*1000:.2f} ms")
    lines = []
    lines.append("")
    lines.append(f"**COLD (fresh cache, full read -- what every tick cost BEFORE the incremental fix): "
                 f"{cold_typical*1000:.1f} ms**")
    lines.append(f"**WARM (cached, no new bytes -- what every tick AFTER the first costs with the fix): "
                 f"{warm_typical*1000:.2f} ms**")
    if warm_typical > 0:
        lines.append(f"speedup (COLD / WARM): {cold_typical / warm_typical:.0f}x")
    return lines


def _extrapolation_lines(cold_typical: float, warm_typical: float) -> list:
    calls_per_second_per_pane = 1.0 / POLL_INTERVAL
    lines = []
    lines.append("")
    lines.append("## Extrapolation to the real call pattern (per-tick cost x ticks/s x 2 panes)")
    lines.append("")
    lines.append(f"`POLL_INTERVAL` = {POLL_INTERVAL}s -> {calls_per_second_per_pane:.0f} refresh ticks/second/pane")
    lines.append("")
    lines.append("| | one pane, ms/s | both panes, ms/s | both panes, % of one core |")
    lines.append("|---|---|---|---|")
    for label, per_call in (("BEFORE the fix (every tick pays COLD)", cold_typical),
                             ("AFTER the fix (every tick pays WARM)", warm_typical)):
        one_pane = per_call * calls_per_second_per_pane * 1000
        both_panes = one_pane * 2
        lines.append(f"| {label} | {one_pane:.1f} | {both_panes:.1f} | {both_panes/10:.2f}% |")
    print(f"BEFORE (cold every tick), both panes: {cold_typical * calls_per_second_per_pane * 2 * 1000:.1f} ms/s")
    print(f"AFTER (warm every tick), both panes: {warm_typical * calls_per_second_per_pane * 2 * 1000:.2f} ms/s")
    return lines


def _stress_test_lines(all_worktree_files: list) -> list:
    largest_size, largest_path = all_worktree_files[0]
    lines = []
    lines.append("")
    lines.append("## Worst-case single file (largest real worker-worktree JSONL found)")
    lines.append("")
    lines.append(f"`{largest_path.name}` -- {largest_size / 1_048_576:.2f} MB")
    result_largest = _time_cold_then_warm([largest_path])
    cold_largest = result_largest['cold_s']
    warm_largest = result_largest['warm_s']
    print(f"attach_worker_stats COLD over the single largest file ({largest_size/1_048_576:.1f} MB): "
          f"{cold_largest*1000:.1f} ms")
    print(f"attach_worker_stats WARM over the same file: {warm_largest*1000:.2f} ms")
    lines.append(f"**COLD: {cold_largest*1000:.1f} ms** -- **WARM: {warm_largest*1000:.2f} ms**")
    if cold_largest > POLL_INTERVAL:
        lines.append("")
        lines.append(f"**COLD alone costs MORE than one POLL_INTERVAL tick ({POLL_INTERVAL}s) -- this is "
                     f"what every tick paid before the fix for a worker this size, and what the FIRST "
                     f"tick after this worker is discovered still pays after it.**")
        print(f"WARNING: COLD cost ({cold_largest:.2f}s) exceeds POLL_INTERVAL ({POLL_INTERVAL}s)")
    if warm_largest > POLL_INTERVAL:
        lines.append(f"**WARM ALSO exceeds POLL_INTERVAL -- the fix does not help this file.**")
        print(f"WARNING: WARM cost ({warm_largest:.2f}s) ALSO exceeds POLL_INTERVAL ({POLL_INTERVAL}s)")
    return lines


def _write_report(lines: list) -> None:
    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'attach_worker_stats_cost_probe_{ts}.md'
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")


if __name__ == '__main__':
    run_probe_workflow()
