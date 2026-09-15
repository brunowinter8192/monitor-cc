"""
p1_full_sweep_cost_probe.py — Milestone 1 measurement probe for the proxy-pane search feature.

Core cost question: the pane keeps `messages=None` for all entries outside the last-10
window (`PROXY_MESSAGES_KEEP_LAST` in `src/constants.py`); searching ALL requests' content
requires reconstructing every entry's messages. Two candidate strategies, measured on a real
forwarded-delta log:

  1. Per-entry lazy-load: replay the forwarded delta stream from byte 0 per entry (mirrors
     `forwarded_parser._lazy_load_messages_forwarded`) — timed for ALL entries, summed + curve.
  2. One-sweep reconstruction: a single pass over the forwarded log that reconstructs and
     KEEPS messages for every entry (mirrors `forwarded_parser._parse_forwarded_log` with its
     deque eviction removed — the parser already walks the whole file for delta accumulation;
     the sweep variant just doesn't discard).

dev/ scripts must not import from src/ — the delta-accumulation algorithm
(`_dict_to_list`/`_apply_delta_to_list`/family accumulator/deque-bound eviction) is
reimplemented locally in p1_full_sweep_reconstruct.py, mirroring
`src/proxy_display/forwarded_parser.py`. Message summarization is simplified to a chars-only
count (real `src/proxy/message_summary.py` adds per-block-type detail — irrelevant to the O(N)
file-replay cost this probe measures, which is dominated by repeated file I/O + json.loads, not
summarizer detail). Both candidate strategies below share this SAME local summarizer, so the
relative comparison is apples-to-apples.

RAM measured via tracemalloc (traced current/peak bytes), isolated per scenario via
gc.collect() + tracemalloc.clear_traces().

Writes dev/pane_search/md/p1_full_sweep_cost_report.md.

Usage (from project root):
    ./venv/bin/python dev/pane_search/p1_full_sweep_cost_probe.py [fwd_log_path]
"""

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
