#!/usr/bin/env python3

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
DEFAULT_PROJECT = None
REPORTS_DIR = Path(__file__).parent / '03_reports'

SEARCH_PATTERNS = [
    ('Contents of', re.compile(r'Contents of ([^\n"\\]{5,100})')),
    ('CLAUDE.md', re.compile(r'CLAUDE\.md')),
    ('.claude/rules/', re.compile(r'\.claude/rules/')),
    ('shared-rules', re.compile(r'shared-rules')),
    ('claudeMd', re.compile(r'claudeMd')),
    ('system-reminder', re.compile(r'<system-reminder>')),
    ('command-message', re.compile(r'<command-message>')),
    ('command-name', re.compile(r'<command-name>')),
    ('InstructionsLoaded', re.compile(r'InstructionsLoaded')),
    ('memory_type', re.compile(r'memory_type')),
]


_SKIPPED_LINES = 0


def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1


def _report_skipped_lines() -> None:
    print(f'skipped undecodable lines: {_SKIPPED_LINES}')


def find_latest_jsonl(project_name: str = None) -> Path:
    if project_name:
        project_dir = PROJECTS_DIR / project_name
    else:
        project_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if not project_dirs:
            raise FileNotFoundError(f"No projects found in {PROJECTS_DIR}")
        project_dir = max(project_dirs, key=lambda d: d.stat().st_mtime)
    if not project_dir.exists():
        raise FileNotFoundError(f"Project dir not found: {project_dir}")
    jsonl_files = sorted(project_dir.glob('*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files in {project_dir}")
    return jsonl_files[0]


def truncate(text: str, max_len: int = 300) -> str:
    if not text:
        return ''
    s = str(text).replace('\n', '\\n')
    if len(s) > max_len:
        return s[:max_len] + '...'
    return s


def extract_content_text(msg: dict) -> str:
    content = msg.get('message', {}).get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if 'text' in block:
                    parts.append(block['text'])
                if 'input' in block and isinstance(block['input'], dict):
                    parts.append(json.dumps(block['input']))
                if 'content' in block:
                    sub = block['content']
                    if isinstance(sub, str):
                        parts.append(sub)
                    elif isinstance(sub, list):
                        for s in sub:
                            if isinstance(s, dict) and 'text' in s:
                                parts.append(s['text'])
        return '\n'.join(parts)
    return ''


def _record_pattern_hits(line: str, line_num: int, msg_type: str, pattern_hits: dict) -> None:
    for name, pattern in SEARCH_PATTERNS:
        matches = pattern.findall(line)
        if matches:
            for match in matches[:3]:
                idx = line.find(str(match))
                context = line[max(0, idx-40):idx+len(str(match))+60]
                pattern_hits[name].append({
                    'line': line_num,
                    'type': msg_type,
                    'match': str(match)[:100],
                    'context': truncate(context, 200),
                })


def _collect_instruction_stats(filepath: Path) -> tuple:
    pattern_hits = {name: [] for name, _ in SEARCH_PATTERNS}
    is_meta_messages = []
    file_history_snapshots = []
    total_lines = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                _note_skipped_line()
                continue

            msg_type = msg.get('type', '?')

            if msg.get('isMeta', False):
                content_text = extract_content_text(msg)
                is_meta_messages.append({
                    'line': line_num,
                    'type': msg_type,
                    'content_preview': truncate(content_text, 500),
                    'content_len': len(content_text),
                    'timestamp': msg.get('timestamp', ''),
                })

            if msg_type == 'file-history-snapshot':
                snapshot = msg.get('snapshot', {})
                file_history_snapshots.append({
                    'line': line_num,
                    'keys': list(msg.keys()),
                    'snapshot_keys': list(snapshot.keys()) if isinstance(snapshot, dict) else str(type(snapshot)),
                    'snapshot_preview': truncate(json.dumps(snapshot, ensure_ascii=False), 500) if snapshot else '-',
                    'is_update': msg.get('isSnapshotUpdate', False),
                })

            _record_pattern_hits(line, line_num, msg_type, pattern_hits)

    return pattern_hits, is_meta_messages, file_history_snapshots, total_lines


def _pattern_summary_lines(pattern_hits: dict) -> list:
    lines = []
    lines.append(f'## Pattern Search Summary')
    lines.append(f'')
    lines.append(f'| Pattern | Hits |')
    lines.append(f'|---------|------|')
    for name, _ in SEARCH_PATTERNS:
        count = len(pattern_hits[name])
        lines.append(f'| `{name}` | {count} |')
    lines.append(f'')
    return lines


def _is_meta_section_lines(is_meta_messages: list) -> list:
    lines = []
    lines.append(f'## isMeta Messages ({len(is_meta_messages)})')
    lines.append(f'')
    if is_meta_messages:
        for entry in is_meta_messages:
            lines.append(f'### Line {entry["line"]} [{entry["type"]}]')
            lines.append(f'')
            lines.append(f'- **Timestamp:** {entry["timestamp"]}')
            lines.append(f'- **Content length:** {entry["content_len"]} chars')
            lines.append(f'- **Preview:**')
            lines.append(f'```')
            lines.append(entry['content_preview'])
            lines.append(f'```')
            lines.append(f'')
    else:
        lines.append('No isMeta messages found.')
        lines.append(f'')
    return lines


def _file_history_section_lines(file_history_snapshots: list) -> list:
    lines = []
    lines.append(f'## file-history-snapshot ({len(file_history_snapshots)})')
    lines.append(f'')
    if file_history_snapshots:
        lines.append(f'| Line | Keys | Snapshot Keys | isUpdate |')
        lines.append(f'|------|------|---------------|----------|')
        for entry in file_history_snapshots[:10]:
            snapshot_keys = ', '.join(entry['snapshot_keys']) if isinstance(entry['snapshot_keys'], list) else entry['snapshot_keys']
            lines.append(f'| {entry["line"]} | {len(entry["keys"])} keys | {truncate(snapshot_keys, 80)} | {entry["is_update"]} |')
        if len(file_history_snapshots) > 10:
            lines.append(f'| ... | +{len(file_history_snapshots)-10} more | | |')
        lines.append(f'')

        lines.append(f'**First snapshot example:**')
        lines.append(f'```json')
        lines.append(file_history_snapshots[0]['snapshot_preview'])
        lines.append(f'```')
        lines.append(f'')
    else:
        lines.append('No file-history-snapshot messages found.')
        lines.append(f'')
    return lines


def _pattern_detail_lines(pattern_hits: dict) -> list:
    lines = []
    for name, _ in SEARCH_PATTERNS:
        hits = pattern_hits[name]
        if not hits:
            continue
        lines.append(f'## Pattern: `{name}` ({len(hits)} hits)')
        lines.append(f'')
        for hit in hits[:15]:
            lines.append(f'- **Line {hit["line"]}** [{hit["type"]}]: `{hit["match"]}`')
            lines.append(f'  Context: `{hit["context"]}`')
        if len(hits) > 15:
            lines.append(f'- ... +{len(hits)-15} more hits')
        lines.append(f'')
    return lines


def scan_jsonl(filepath: Path) -> str:
    pattern_hits, is_meta_messages, file_history_snapshots, total_lines = _collect_instruction_stats(filepath)

    lines = []
    lines.append(f'# JSONL Instructions & Rules Scan')
    lines.append(f'')
    lines.append(f'**Source:** `{filepath.name}` ({filepath.stat().st_size:,} bytes)')
    lines.append(f'**Scanned:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'**Total lines:** {total_lines}')
    lines.append(f'')

    lines.extend(_pattern_summary_lines(pattern_hits))
    lines.extend(_is_meta_section_lines(is_meta_messages))
    lines.extend(_file_history_section_lines(file_history_snapshots))
    lines.extend(_pattern_detail_lines(pattern_hits))

    return '\n'.join(lines)


def main():
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    else:
        filepath = find_latest_jsonl(DEFAULT_PROJECT)

    report = scan_jsonl(filepath)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = REPORTS_DIR / f'instructions_{timestamp}.md'
    output_path.write_text(report, encoding='utf-8')
    print(f'Report written to: {output_path}')
    _report_skipped_lines()


if __name__ == '__main__':
    main()
