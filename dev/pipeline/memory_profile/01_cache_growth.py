# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
Path('src/logs').mkdir(parents=True, exist_ok=True)

from src.jsonl_parser import parse_jsonl_lines, extract_tool_calls

REPORTS_DIR = Path(__file__).parent / '01_reports'
CHECKPOINT_INTERVAL = 100


# ORCHESTRATOR
def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_file = find_newest_jsonl()
    if not jsonl_file:
        print('ERROR: No JSONL files found in ~/.claude/projects/')
        sys.exit(1)

    lines = read_all_lines(jsonl_file)
    checkpoints, orphaned = measure_cache_growth(lines)
    report_path = write_report(jsonl_file, lines, checkpoints, orphaned)
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


# Feed lines through parser in batches and snapshot cache size at each checkpoint
def measure_cache_growth(lines):
    checkpoints = []
    cache = {}
    processed = 0

    for i in range(0, len(lines), CHECKPOINT_INTERVAL):
        batch = lines[i:i + CHECKPOINT_INTERVAL]
        messages, _ = parse_jsonl_lines(batch)
        extract_tool_calls(messages, cache)
        processed += len(batch)

        checkpoints.append({
            'messages_processed': processed,
            'cache_entries': len(cache),
            'cache_size_bytes': sys.getsizeof(cache),
        })

    orphaned = list(cache.values())
    return checkpoints, orphaned


# Write MD report and return path
def write_report(jsonl_file, lines, checkpoints, orphaned):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORTS_DIR / f'cache_growth_{timestamp}.md'

    peak_entries = max((cp['cache_entries'] for cp in checkpoints), default=0)
    total_messages = len(lines)

    max_size = max((cp['cache_size_bytes'] for cp in checkpoints), default=0)
    estimated_per_1000 = int(max_size / total_messages * 1000) if total_messages > 0 else 0

    out = []
    out.append('# Cache Growth Profile')
    out.append(f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    out.append(f'Session: {jsonl_file.name}')
    out.append(f'Messages: {total_messages}')
    out.append('')
    out.append('## tool_use_cache Growth')
    out.append('| Messages Processed | Cache Entries | Cache Size (bytes) |')
    out.append('|---|---|---|')
    for cp in checkpoints:
        out.append(f'| {cp["messages_processed"]} | {cp["cache_entries"]} | {cp["cache_size_bytes"]} |')
    out.append('')
    out.append('## Orphaned Entries at End')
    out.append('| tool_use_id | tool_name | timestamp |')
    out.append('|---|---|---|')
    for entry in orphaned:
        out.append(f'| {entry.get("tool_use_id", "")} | {entry.get("tool_name", "")} | {entry.get("timestamp", "")} |')
    out.append('')
    out.append('## Summary')
    out.append(f'- Peak cache entries: {peak_entries}')
    out.append(f'- Final orphaned entries: {len(orphaned)}')
    out.append(f'- Estimated memory per 1000 messages: {estimated_per_1000} bytes')

    report_path.write_text('\n'.join(out) + '\n')
    return report_path


if __name__ == '__main__':
    main()
