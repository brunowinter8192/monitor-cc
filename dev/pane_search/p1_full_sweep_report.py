# INFRASTRUCTURE
from p1_full_sweep_reconstruct import _infer_model_family

_SEARCH_BUDGET_S = 1.0
_KEEP_LAST_BASELINE = 10

# FUNCTIONS

def _linear_fit(values: list) -> tuple:
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept

def _log_stats(entries: list) -> dict:
    families = sorted({_infer_model_family(e['model']) for e in entries})
    final_msg_count_by_family = {}
    for family in families:
        fam_entries = [e for e in entries if _infer_model_family(e['model']) == family]
        final_msg_count_by_family[family] = fam_entries[-1]['message_count']
    return {
        'n_entries': len(entries),
        'families': families,
        'final_msg_count_by_family': final_msg_count_by_family,
        'total_messages_total_chars': sum(e['messages_total_chars'] for e in entries),
    }

def _compute_report_metrics(stats: dict, base_elapsed: float, base_current: int, base_peak: int,
                             sweep_elapsed: float, sweep_current: int, sweep_peak: int,
                             lazy_times: list) -> dict:
    n = stats['n_entries']
    lazy_sum = sum(lazy_times)
    slope, intercept = _linear_fit(lazy_times)
    fam_line = ', '.join(f"{fam}={cnt}" for fam, cnt in stats['final_msg_count_by_family'].items())
    sample_idxs = sorted(set([0, n // 4, n // 2, (3 * n) // 4, n - 1]))
    sample_rows = '\n'.join(f"| {i} | {lazy_times[i] * 1000:.3f} |" for i in sample_idxs)
    first10_avg = sum(lazy_times[:10]) / min(10, n) * 1000
    last10_avg = sum(lazy_times[-10:]) / min(10, n) * 1000
    growth_ratio = (last10_avg / first10_avg) if first10_avg else float('inf')
    speedup = lazy_sum / sweep_elapsed if sweep_elapsed else float('inf')
    ram_delta_kb = (sweep_current - base_current) / 1024
    ram_peak_delta_kb = (sweep_peak - base_peak) / 1024
    lazy_viable = lazy_sum <= _SEARCH_BUDGET_S
    sweep_viable = sweep_elapsed <= _SEARCH_BUDGET_S
    n_at_budget = int((_SEARCH_BUDGET_S / slope) ** 0.5) if slope > 0 else None
    return {
        'n': n, 'lazy_sum': lazy_sum, 'slope': slope, 'intercept': intercept, 'fam_line': fam_line,
        'sample_rows': sample_rows, 'first10_avg': first10_avg, 'last10_avg': last10_avg,
        'growth_ratio': growth_ratio, 'speedup': speedup, 'ram_delta_kb': ram_delta_kb,
        'ram_peak_delta_kb': ram_peak_delta_kb, 'lazy_viable': lazy_viable, 'sweep_viable': sweep_viable,
        'n_at_budget': n_at_budget, 'base_elapsed': base_elapsed, 'base_current': base_current,
        'base_peak': base_peak, 'sweep_elapsed': sweep_elapsed, 'sweep_current': sweep_current,
        'sweep_peak': sweep_peak,
    }

def _build_report_header(fwd_path, file_size_bytes: int, stats: dict, metrics: dict) -> str:
    n = metrics['n']
    fam_line = metrics['fam_line']
    return f"""# P1 — Full-Sweep Reconstruction Cost Probe

Milestone 1 measurement for the proxy-pane search feature (`src/proxy_display/`). Compares
per-entry lazy-load (replay-from-0 per entry, mirrors `_lazy_load_messages_forwarded`) against
one-sweep reconstruction (single pass, deque bound removed, mirrors `_parse_forwarded_log`) for
the cost of making ALL entries' messages searchable. No feature code — measurement only.

Methodology note: dev/ scripts must not import `src/`, so the delta-accumulation algorithm is
reimplemented locally in this probe (`_sweep_parse`/`_lazy_load_one`), mirroring
`src/proxy_display/forwarded_parser.py`'s `_parse_forwarded_log`/`_lazy_load_messages_forwarded`
structurally (same per-line I/O + json.loads + delta-apply work). Message summarization is
simplified to chars-only (real `_summarize_message` adds per-block-type detail irrelevant to the
O(N) file-replay cost measured here); both strategies below share this same local summarizer.

## Log measured

- File: `{fwd_path.name}`
- Path: `{fwd_path}`
- Size: {file_size_bytes:,} bytes ({file_size_bytes / 1e6:.2f} MB)
- `forwarded_delta` entries (N): {n}
- Model families present: {', '.join(stats['families'])}
- Final `message_count` per family (conversation length at last entry): {fam_line}
- Aggregate `messages_total_chars` summed over all {n} entries: {stats['total_messages_total_chars']:,} chars"""

def _build_wall_time_section(metrics: dict) -> str:
    n = metrics['n']
    return f"""## Wall time

| Strategy | Total wall time | Within {_SEARCH_BUDGET_S:.0f}s interactive budget? |
|---|---|---|
| Per-entry lazy-load, ALL {n} entries (sum) | {metrics['lazy_sum'] * 1000:.1f} ms | {'YES' if metrics['lazy_viable'] else 'NO'} |
| One-sweep reconstruction (single pass, all entries retained) | {metrics['sweep_elapsed'] * 1000:.2f} ms | {'YES' if metrics['sweep_viable'] else 'NO'} |
| Baseline: current parse behavior (keep-last-{_KEEP_LAST_BASELINE} window) | {metrics['base_elapsed'] * 1000:.2f} ms | YES |

One-sweep is **{metrics['speedup']:.0f}x faster** than summed per-entry lazy-load for N={n}.

**Per-entry lazy-load curve — does cost grow with entry index?**

Linear fit over per-entry replay time vs entry index: slope = {metrics['slope'] * 1000:.4f} ms/index-step,
intercept = {metrics['intercept'] * 1000:.4f} ms. First-10-entries avg = {metrics['first10_avg']:.3f} ms;
last-10-entries avg = {metrics['last10_avg']:.3f} ms → **{metrics['growth_ratio']:.0f}x growth** from first to last
entry — consistent with the O(idx) replay-from-0 cost per call, i.e. summed cost is O(N^2).

| entry idx | lazy-load time (ms) |
|---|---|
{metrics['sample_rows']}"""

def _build_ram_section(stats: dict, metrics: dict) -> str:
    n = metrics['n']
    return f"""## Peak RAM

Traced via `tracemalloc`, isolated per scenario (`gc.collect()` + `clear_traces()` before each
parse). "Baseline" = current production behavior (keep-last-{_KEEP_LAST_BASELINE},
messages=None outside the window). "One-sweep" = same parse, deque bound removed (all N entries
retain messages simultaneously).

| Scenario | Traced current | Traced peak |
|---|---|---|
| Baseline (keep-last-{_KEEP_LAST_BASELINE}) | {metrics['base_current'] / 1024:.1f} KB | {metrics['base_peak'] / 1024:.1f} KB |
| One-sweep (all {n} entries retained) | {metrics['sweep_current'] / 1024:.1f} KB | {metrics['sweep_peak'] / 1024:.1f} KB |
| **Delta (one-sweep minus baseline)** | **{metrics['ram_delta_kb']:+.1f} KB** | **{metrics['ram_peak_delta_kb']:+.1f} KB** |

The delta is a modest {metrics['ram_delta_kb']:.0f} KB in absolute terms — not because per-entry content is
small (aggregate `messages_total_chars` summed across all {n} entries is
{stats['total_messages_total_chars']:,} chars, since each entry's total counts its WHOLE
cumulative conversation at that point), but because unchanged messages are already reused across
accumulator snapshots (each new_summaries list is a shallow copy of the previous one — untouched
indices keep pointing at the same summary dict object, mirroring the sharing behavior documented
in `forwarded_parser.py`'s own comment on `_parse_forwarded_log`). Retaining `entry['messages']`
for all N entries mostly retains N extra *list* objects pointing at already-live summary dicts,
not N independent copies of the conversation content — without that sharing, one-sweep's RAM
cost would be orders of magnitude higher."""

def _build_conclusion_section(file_size_bytes: int, metrics: dict) -> str:
    n = metrics['n']
    return f"""## Conclusion

For N={n} entries ({file_size_bytes / 1e6:.1f} MB forwarded log): per-entry lazy-load of ALL
entries costs {metrics['lazy_sum'] * 1000:.0f} ms ({'over' if not metrics['lazy_viable'] else 'under'} the
~{_SEARCH_BUDGET_S:.0f}s interactive budget), growing ~quadratically with entry count —
**not viable** as a search-triggered operation past roughly N={metrics['n_at_budget']} entries (crude
estimate from the observed per-entry linear-growth slope: total-time ~ slope * N^2 / 2 = budget).

One-sweep reconstruction costs {metrics['sweep_elapsed'] * 1000:.1f} ms for the same log — **well within**
the 1s budget, and its RAM cost over the current keep-last-{_KEEP_LAST_BASELINE} baseline is
marginal ({metrics['ram_delta_kb']:+.1f} KB) thanks to the accumulator's existing shared-reference pattern.
It scales with file size, not N^2 — for logs an order of magnitude larger than this one,
one-sweep should stay well under budget while per-entry lazy-load would not.

**Cache-after-first-sweep:** given one-sweep is already comfortably fast for this real log, a
cache is not required to hit the 1s budget at this scale. It becomes worth adding once forwarded
logs grow large enough (multi-session, multi-MB) that a single sweep approaches the budget on
every Enter keypress — caching the sweep result keyed on file byte-position (re-sweep only the
delta since last cache) would keep repeat searches near-instant without re-reading the whole file.
"""

def _build_report_md(fwd_path, file_size_bytes: int, stats: dict,
                      base_elapsed: float, base_current: int, base_peak: int,
                      sweep_elapsed: float, sweep_current: int, sweep_peak: int,
                      lazy_times: list) -> str:
    metrics = _compute_report_metrics(stats, base_elapsed, base_current, base_peak,
                                       sweep_elapsed, sweep_current, sweep_peak, lazy_times)
    return '\n\n'.join([
        _build_report_header(fwd_path, file_size_bytes, stats, metrics),
        _build_wall_time_section(metrics),
        _build_ram_section(stats, metrics),
        _build_conclusion_section(file_size_bytes, metrics),
    ])
