# INFRASTRUCTURE
import gc
import sys
import tracemalloc
from pathlib import Path

from p1_full_sweep_reconstruct import _traced_sweep, _measure_lazy_load_all
from p1_full_sweep_report import _KEEP_LAST_BASELINE, _log_stats, _build_report_md

_DEFAULT_FWD_LOG = Path(
    '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/'
    'api_requests_opus_wise2627_1786984319_forwarded.jsonl'
)
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p1_full_sweep_cost_report.md'

# ORCHESTRATOR

def probe_workflow(fwd_path: Path) -> None:
    if not fwd_path.exists():
        raise FileNotFoundError(f'forwarded log not found: {fwd_path}')
    tracemalloc.start()
    file_size_bytes = fwd_path.stat().st_size

    base_entries, base_elapsed, base_current, base_peak = _traced_sweep(fwd_path, _KEEP_LAST_BASELINE)
    stats = _log_stats(base_entries)

    lazy_times = _measure_lazy_load_all(base_entries, fwd_path)
    del base_entries
    gc.collect()

    sweep_entries, sweep_elapsed, sweep_current, sweep_peak = _traced_sweep(fwd_path, None)
    del sweep_entries
    gc.collect()

    report_md = _build_report_md(
        fwd_path, file_size_bytes, stats,
        base_elapsed, base_current, base_peak,
        sweep_elapsed, sweep_current, sweep_peak,
        lazy_times,
    )
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(report_md, encoding='utf-8')
    print(f'entries={stats["n_entries"]} lazy_sum_ms={sum(lazy_times) * 1000:.1f} '
          f'sweep_ms={sweep_elapsed * 1000:.2f} ram_delta_kb={(sweep_current - base_current) / 1024:+.1f}')
    print(f'Report written to {_REPORT_PATH}')


if __name__ == '__main__':
    _arg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_FWD_LOG
    probe_workflow(_arg_path)
