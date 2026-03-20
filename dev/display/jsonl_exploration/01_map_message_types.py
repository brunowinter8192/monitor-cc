#!/usr/bin/env python3
"""Map all message types in a Claude Code session JSONL.

For each message type: count, top-level keys, subtypes, isMeta distribution,
and one truncated example.

Usage:
    python3 dev/display/jsonl_exploration/01_map_message_types.py [path/to/session.jsonl]

Default: latest JSONL from RAG project.
Output: dev/display/jsonl_exploration/01_reports/message_types_<timestamp>.md
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
DEFAULT_PROJECT = '-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-RAG'
REPORTS_DIR = Path(__file__).parent / '01_reports'


def find_latest_jsonl(project_name: str) -> Path:
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise FileNotFoundError(f"Project dir not found: {project_dir}")
    jsonl_files = sorted(project_dir.glob('*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files in {project_dir}")
    return jsonl_files[0]


def truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ''
    s = str(text).replace('\n', '\\n')
    if len(s) > max_len:
        return s[:max_len] + '...'
    return s


def scan_jsonl(filepath: Path) -> str:
    type_counts = Counter()
    type_keys = defaultdict(set)
    type_subtypes = defaultdict(set)
    type_is_meta = defaultdict(Counter)
    type_examples = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get('type', 'MISSING')
            type_counts[msg_type] += 1
            type_keys[msg_type].update(msg.keys())

            if 'subtype' in msg:
                type_subtypes[msg_type].add(msg['subtype'])

            is_meta = msg.get('isMeta', None)
            type_is_meta[msg_type][str(is_meta)] += 1

            if msg_type not in type_examples:
                type_examples[msg_type] = msg

    lines = []
    lines.append(f'# JSONL Message Types')
    lines.append(f'')
    lines.append(f'**Source:** `{filepath.name}` ({filepath.stat().st_size:,} bytes)')
    lines.append(f'**Scanned:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'**Total messages:** {sum(type_counts.values())}')
    lines.append(f'')

    lines.append(f'## Summary')
    lines.append(f'')
    lines.append(f'| Type | Count | Subtypes | isMeta |')
    lines.append(f'|------|-------|----------|--------|')
    for msg_type, count in type_counts.most_common():
        subtypes = ', '.join(sorted(type_subtypes[msg_type])) if type_subtypes[msg_type] else '-'
        meta_dist = ', '.join(f'{k}:{v}' for k, v in sorted(type_is_meta[msg_type].items()) if k != 'None')
        if not meta_dist:
            meta_dist = '-'
        lines.append(f'| `{msg_type}` | {count} | {subtypes} | {meta_dist} |')

    lines.append(f'')

    for msg_type, count in type_counts.most_common():
        lines.append(f'## `{msg_type}` ({count}x)')
        lines.append(f'')
        lines.append(f'**Keys:** `{"`, `".join(sorted(type_keys[msg_type]))}`')
        lines.append(f'')

        if type_subtypes[msg_type]:
            lines.append(f'**Subtypes:** {", ".join(sorted(type_subtypes[msg_type]))}')
            lines.append(f'')

        example = type_examples[msg_type]
        lines.append(f'**Example (truncated):**')
        lines.append(f'```json')
        example_clean = {}
        for k, v in example.items():
            if k == 'message':
                msg_obj = v
                content = msg_obj.get('content', '')
                if isinstance(content, str):
                    msg_obj = {**msg_obj, 'content': truncate(content)}
                elif isinstance(content, list):
                    truncated_content = []
                    for block in content[:3]:
                        if isinstance(block, dict):
                            tb = {}
                            for bk, bv in block.items():
                                tb[bk] = truncate(str(bv)) if isinstance(bv, str) and len(str(bv)) > 200 else bv
                            truncated_content.append(tb)
                        else:
                            truncated_content.append(block)
                    if len(content) > 3:
                        truncated_content.append(f'... +{len(content)-3} more blocks')
                    msg_obj = {**msg_obj, 'content': truncated_content}
                example_clean[k] = msg_obj
            elif isinstance(v, str) and len(v) > 200:
                example_clean[k] = truncate(v)
            else:
                example_clean[k] = v
        lines.append(json.dumps(example_clean, indent=2, ensure_ascii=False))
        lines.append(f'```')
        lines.append(f'')

    return '\n'.join(lines)


def main():
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    else:
        filepath = find_latest_jsonl(DEFAULT_PROJECT)

    report = scan_jsonl(filepath)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = REPORTS_DIR / f'message_types_{timestamp}.md'
    output_path.write_text(report, encoding='utf-8')
    print(f'Report written to: {output_path}')


if __name__ == '__main__':
    main()
