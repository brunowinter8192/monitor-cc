# INFRASTRUCTURE
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

REPORTS_DIR = Path(__file__).parent / '01_reports'

KNOWN_TOP_LEVEL_TYPES = {'assistant', 'user', 'progress', 'result', 'system'}
KNOWN_CONTENT_BLOCK_TYPES = {'tool_use', 'tool_result', 'text', 'thinking', 'image', 'document'}


# ORCHESTRATOR
def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_files = find_all_jsonl_files()
    if not jsonl_files:
        print('ERROR: No JSONL files found in ~/.claude/projects/')
        sys.exit(1)

    scan_result = scan_all_files(jsonl_files)
    report_path = write_report(scan_result)
    print(report_path)


# FUNCTIONS

# Find all JSONL files in ~/.claude/projects/
def find_all_jsonl_files():
    claude_dir = Path.home() / '.claude' / 'projects'
    if not claude_dir.exists():
        return []
    return list(claude_dir.glob('**/*.jsonl'))


# Scan all files, collect message type counts, content block types, unknowns, versions
def scan_all_files(jsonl_files):
    top_level_types = Counter()
    content_block_types = Counter()
    unknown_top = {}
    unknown_content = {}
    parse_errors = 0
    total_lines = 0
    version_counter = Counter()

    for filepath in jsonl_files:
        try:
            lines = filepath.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue

        for line in lines:
            if not line.strip():
                continue
            total_lines += 1
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            msg_type = msg.get('type', 'missing')
            top_level_types[msg_type] += 1

            if msg_type not in KNOWN_TOP_LEVEL_TYPES and msg_type not in unknown_top:
                unknown_top[msg_type] = {
                    'file': filepath.name,
                    'example': line[:200],
                }

            extract_content_block_types(msg, msg_type, content_block_types, unknown_content, filepath)
            collect_version(msg, version_counter)

    return {
        'files_scanned': len(jsonl_files),
        'total_lines': total_lines,
        'parse_errors': parse_errors,
        'top_level_types': top_level_types,
        'content_block_types': content_block_types,
        'unknown_top': unknown_top,
        'unknown_content': unknown_content,
        'versions': version_counter,
    }


# Extract content block types from a single message into the counter
def extract_content_block_types(msg, msg_type, counter, unknown_dict, filepath):
    content_blocks = get_content_blocks(msg, msg_type)
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get('type', 'missing')
        counter[block_type] += 1
        if block_type not in KNOWN_CONTENT_BLOCK_TYPES and block_type not in unknown_dict:
            unknown_dict[block_type] = {
                'file': filepath.name,
                'example': json.dumps(block)[:200],
            }


# Get content blocks list from a message (handles assistant/user and progress nesting)
def get_content_blocks(msg, msg_type):
    if msg_type == 'progress':
        data = msg.get('data', {})
        inner = data.get('message', {})
        inner_inner = inner.get('message', {})
        content = inner_inner.get('content', [])
    elif msg_type in ('assistant', 'user'):
        message_obj = msg.get('message', msg)
        content = message_obj.get('content', [])
    else:
        content = msg.get('content', [])

    if isinstance(content, list):
        return content
    return []


# Collect version info from result-type messages or other known fields
def collect_version(msg, version_counter):
    version = msg.get('version') or msg.get('clientVersion') or msg.get('claude_code_version')
    if version:
        version_counter[str(version)] += 1


# Write MD report and return path
def write_report(data):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = REPORTS_DIR / f'unknown_types_{timestamp}.md'

    total_top = sum(data['top_level_types'].values())
    known_top_count = sum(v for k, v in data['top_level_types'].items() if k in KNOWN_TOP_LEVEL_TYPES)
    top_coverage = known_top_count / total_top * 100 if total_top > 0 else 0

    total_content = sum(data['content_block_types'].values())
    known_content_count = sum(v for k, v in data['content_block_types'].items() if k in KNOWN_CONTENT_BLOCK_TYPES)
    content_coverage = known_content_count / total_content * 100 if total_content > 0 else 0

    out = []
    out.append('# Format Stability Scan')
    out.append(f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    out.append(f'Files scanned: {data["files_scanned"]}')
    out.append(f'Total lines parsed: {data["total_lines"]}')
    out.append(f'Parse errors: {data["parse_errors"]}')
    out.append('')
    out.append('## Top-Level Message Types')
    out.append('| Type | Count | Handled by Parser? |')
    out.append('|---|---|---|')
    for msg_type, count in sorted(data['top_level_types'].items(), key=lambda x: -x[1]):
        handled = 'Yes' if msg_type in KNOWN_TOP_LEVEL_TYPES else 'NO'
        out.append(f'| {msg_type} | {count} | {handled} |')
    out.append('')
    out.append('## Content Block Types')
    out.append('| Type | Count | Handled? |')
    out.append('|---|---|---|')
    for block_type, count in sorted(data['content_block_types'].items(), key=lambda x: -x[1]):
        handled = 'Yes' if block_type in KNOWN_CONTENT_BLOCK_TYPES else 'NO'
        out.append(f'| {block_type} | {count} | {handled} |')
    out.append('')
    out.append('## Unknown Types (Detail)')
    out.append('| Type | File | Example (first 200 chars) |')
    out.append('|---|---|---|')
    for msg_type, info in data['unknown_top'].items():
        example = info['example'].replace('|', '\\|')
        out.append(f'| {msg_type} (top) | {info["file"]} | {example} |')
    for block_type, info in data['unknown_content'].items():
        example = info['example'].replace('|', '\\|')
        out.append(f'| {block_type} (content) | {info["file"]} | {example} |')
    out.append('')
    out.append('## Claude Code Versions Found')
    out.append('| Version | Count | Files |')
    out.append('|---|---|---|')
    if data['versions']:
        for version, count in sorted(data['versions'].items(), key=lambda x: -x[1]):
            out.append(f'| {version} | {count} | |')
    else:
        out.append('| (none found) | | |')
    out.append('')
    out.append('## Summary')
    out.append(f'- Known top-level type coverage: {top_coverage:.1f}%')
    out.append(f'- Known content block coverage: {content_coverage:.1f}%')
    out.append(f'- Unknown top-level types found: {len(data["unknown_top"])}')
    out.append(f'- Unknown content block types found: {len(data["unknown_content"])}')
    if data['unknown_top'] or data['unknown_content']:
        out.append('- Recommendation: review unknown types above and add handling to parser if needed')
    else:
        out.append('- Recommendation: parser handles all observed types')

    report_path.write_text('\n'.join(out) + '\n')
    return report_path


if __name__ == '__main__':
    main()
