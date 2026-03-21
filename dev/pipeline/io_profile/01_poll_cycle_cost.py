# INFRASTRUCTURE
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
Path('src/logs').mkdir(parents=True, exist_ok=True)

from src.session_finder import find_active_sessions

REPORTS_DIR = Path(__file__).parent / '01_reports'
N_CYCLES = 10

# Capture originals before any patching
_orig_stat = Path.stat
_orig_iterdir = Path.iterdir
_orig_glob = Path.glob

_counters = {'stat': 0, 'iterdir': 0, 'glob': 0}


def _counting_stat(self, *, follow_symlinks=True):
    _counters['stat'] += 1
    return _orig_stat(self, follow_symlinks=follow_symlinks)


def _counting_iterdir(self):
    _counters['iterdir'] += 1
    return _orig_iterdir(self)


def _counting_glob(self, pattern, **kwargs):
    _counters['glob'] += 1
    return _orig_glob(self, pattern, **kwargs)


# ORCHESTRATOR
def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    total_projects = count_projects()
    total_jsonl = count_jsonl_files()

    results_unfiltered = run_cycles(None, N_CYCLES)
    results_filtered = run_cycles('Monitor_CC', N_CYCLES)

    report_path = write_report(total_projects, total_jsonl, results_unfiltered, results_filtered)
    print(report_path)


# FUNCTIONS

# Count project directories in ~/.claude/projects
def count_projects():
    claude_dir = Path.home() / '.claude' / 'projects'
    if not claude_dir.exists():
        return 0
    return sum(1 for d in claude_dir.iterdir() if d.is_dir())


# Count all JSONL files in ~/.claude/projects
def count_jsonl_files():
    claude_dir = Path.home() / '.claude' / 'projects'
    if not claude_dir.exists():
        return 0
    return sum(1 for _ in claude_dir.glob('**/*.jsonl'))


# Run N poll cycles with call counting and timing, return stats dict
def run_cycles(project_filter, n_cycles):
    durations = []
    stat_counts = []
    iterdir_counts = []
    glob_counts = []

    Path.stat = _counting_stat
    Path.iterdir = _counting_iterdir
    Path.glob = _counting_glob

    for _ in range(n_cycles):
        _counters['stat'] = 0
        _counters['iterdir'] = 0
        _counters['glob'] = 0

        start = time.perf_counter()
        find_active_sessions(project_filter)
        elapsed_ms = (time.perf_counter() - start) * 1000

        durations.append(elapsed_ms)
        stat_counts.append(_counters['stat'])
        iterdir_counts.append(_counters['iterdir'])
        glob_counts.append(_counters['glob'])

    Path.stat = _orig_stat
    Path.iterdir = _orig_iterdir
    Path.glob = _orig_glob

    return {
        'duration': summarize(durations),
        'stat': summarize(stat_counts),
        'iterdir': summarize(iterdir_counts),
        'glob': summarize(glob_counts),
    }


# Compute mean/stdev/min/max for a list of numbers
def summarize(values):
    return {
        'mean': statistics.mean(values),
        'stdev': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'max': max(values),
    }


# Format a stats dict row for the report table
def fmt_row(label, stats, unit=''):
    mean = f'{stats["mean"]:.2f}{unit}'
    stdev = f'{stats["stdev"]:.2f}{unit}'
    mn = f'{stats["min"]:.2f}{unit}'
    mx = f'{stats["max"]:.2f}{unit}'
    return f'| {label} | {mean} | {stdev} | {mn} | {mx} |'


# Write MD report and return path
def write_report(total_projects, total_jsonl, unfiltered, filtered):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORTS_DIR / f'poll_cycle_{timestamp}.md'

    out = []
    out.append('# Poll Cycle I/O Profile')
    out.append(f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    out.append(f'Projects in ~/.claude/projects/: {total_projects}')
    out.append(f'JSONL files total: {total_jsonl}')
    out.append('')
    out.append('## Without Project Filter')
    out.append('| Metric | Mean | StdDev | Min | Max |')
    out.append('|---|---|---|---|---|')
    out.append(fmt_row('Cycle duration (ms)', unfiltered['duration'], ''))
    out.append(fmt_row('stat() calls', unfiltered['stat'], ''))
    out.append(fmt_row('iterdir() calls', unfiltered['iterdir'], ''))
    out.append(fmt_row('glob() calls', unfiltered['glob'], ''))
    out.append('')
    out.append('## With Project Filter (Monitor_CC)')
    out.append('| Metric | Mean | StdDev | Min | Max |')
    out.append('|---|---|---|---|---|')
    out.append(fmt_row('Cycle duration (ms)', filtered['duration'], ''))
    out.append(fmt_row('stat() calls', filtered['stat'], ''))
    out.append(fmt_row('iterdir() calls', filtered['iterdir'], ''))
    out.append(fmt_row('glob() calls', filtered['glob'], ''))
    out.append('')
    out.append('## Summary')
    out.append(f'- Discovery overhead per cycle: {unfiltered["duration"]["mean"]:.2f} ms')
    out.append(f'- stat() calls per cycle: {unfiltered["stat"]["mean"]:.0f}')
    out.append(f'- Filter reduces cycle duration by: {unfiltered["duration"]["mean"] - filtered["duration"]["mean"]:.2f} ms')

    report_path.write_text('\n'.join(out) + '\n')
    return report_path


if __name__ == '__main__':
    main()
