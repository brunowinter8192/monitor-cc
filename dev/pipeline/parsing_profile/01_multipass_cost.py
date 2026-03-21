# INFRASTRUCTURE
import statistics
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
Path('src/logs').mkdir(parents=True, exist_ok=True)

from src.jsonl_parser import (
    parse_jsonl_lines,
    extract_tool_calls,
    extract_user_prompts,
    extract_user_media,
    extract_thinking_blocks,
    extract_skill_activations,
)

REPORTS_DIR = Path(__file__).parent / '01_reports'
N_RUNS = 10


# ORCHESTRATOR
def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_file = find_newest_jsonl()
    if not jsonl_file:
        print('ERROR: No JSONL files found in ~/.claude/projects/')
        sys.exit(1)

    lines = read_all_lines(jsonl_file)
    messages, _ = parse_jsonl_lines(lines)
    type_dist = count_message_types(messages)
    timings = measure_extract_functions(messages, N_RUNS)
    report_path = write_report(jsonl_file, messages, type_dist, timings)
    print(report_path)


# FUNCTIONS

# Find the newest JSONL file across all project dirs
def find_newest_jsonl():
    claude_dir = Path.home() / '.claude' / 'projects'
    if not claude_dir.exists():
        return None
    files = list(claude_dir.glob('**/*.jsonl'))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


# Read all lines from file as list of strings
def read_all_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    if lines and not lines[-1]:
        lines = lines[:-1]
    return lines


# Count message types from parsed messages
def count_message_types(messages):
    return Counter(m.get('type', 'unknown') for m in messages)


# Time each extract function N_RUNS times, return per-function stats in microseconds
def measure_extract_functions(messages, n_runs):
    functions = [
        ('extract_tool_calls', lambda: extract_tool_calls(messages, {})),
        ('extract_user_prompts', lambda: extract_user_prompts(messages)),
        ('extract_user_media', lambda: extract_user_media(messages)),
        ('extract_thinking_blocks', lambda: extract_thinking_blocks(messages)),
        ('extract_skill_activations', lambda: extract_skill_activations(messages)),
    ]

    results = []
    for name, fn in functions:
        samples = []
        for _ in range(n_runs):
            start = time.perf_counter()
            fn()
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            samples.append(elapsed_us)
        results.append({
            'name': name,
            'mean': statistics.mean(samples),
            'stdev': statistics.stdev(samples) if len(samples) > 1 else 0.0,
        })

    return results


# Write MD report and return path
def write_report(jsonl_file, messages, type_dist, timings):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORTS_DIR / f'multipass_{timestamp}.md'

    total_us = sum(t['mean'] for t in timings)
    n_messages = len(messages)

    out = []
    out.append('# Multi-Pass Parsing Profile')
    out.append(f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    out.append(f'Session: {jsonl_file.name}')
    out.append(f'Messages: {n_messages}')
    out.append('')
    out.append('## Per-Function Timing (10 runs, microseconds)')
    out.append('| Function | Mean | StdDev | % of Total |')
    out.append('|---|---|---|---|')
    for t in timings:
        pct = (t['mean'] / total_us * 100) if total_us > 0 else 0
        out.append(f'| {t["name"]} | {t["mean"]:.1f} | {t["stdev"]:.1f} | {pct:.1f}% |')
    out.append(f'| **Total (5 passes)** | {total_us:.1f} | | 100% |')
    out.append('')
    out.append('## Message Type Distribution')
    out.append('| Type | Count | % |')
    out.append('|---|---|---|')
    for msg_type, count in sorted(type_dist.items(), key=lambda x: -x[1]):
        pct = count / n_messages * 100 if n_messages > 0 else 0
        out.append(f'| {msg_type} | {count} | {pct:.1f}% |')
    out.append('')
    out.append('## Summary')
    out.append(f'- Total parsing time for {n_messages} messages: {total_us:.1f} us')
    avg_per_msg = total_us / n_messages if n_messages > 0 else 0
    out.append(f'- Average per message: {avg_per_msg:.2f} us')
    iteration_overhead_per_pass = n_messages * 0.05
    single_pass_estimate = total_us - (iteration_overhead_per_pass * 4)
    out.append(f'- Single-pass savings estimate: {max(0, total_us - single_pass_estimate):.1f} us (based on iteration overhead)')

    report_path.write_text('\n'.join(out) + '\n')
    return report_path


if __name__ == '__main__':
    main()
