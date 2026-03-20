#!/usr/bin/env python3
"""Map content block types in a Claude Code session JSONL.

For each msg_type/content_type combination: count, keys, nested structure,
tool names, and one truncated example.

Usage:
    python3 dev/display/jsonl_exploration/02_map_content_blocks.py [path/to/session.jsonl]

Default: latest JSONL from RAG project.
Output: dev/display/jsonl_exploration/02_reports/content_blocks_<timestamp>.md
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
DEFAULT_PROJECT = '-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-RAG'
REPORTS_DIR = Path(__file__).parent / '02_reports'


def find_latest_jsonl(project_name: str) -> Path:
    project_dir = PROJECTS_DIR / project_name
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


def describe_nested(obj, depth=0, max_depth=3) -> list:
    """Recursively describe nested structure."""
    lines = []
    indent = '  ' * depth
    if depth >= max_depth:
        lines.append(f'{indent}...')
        return lines
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                lines.append(f'{indent}{k}: dict')
                lines.extend(describe_nested(v, depth + 1, max_depth))
            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    lines.append(f'{indent}{k}: list[dict] ({len(v)} items)')
                    lines.extend(describe_nested(v[0], depth + 1, max_depth))
                else:
                    lines.append(f'{indent}{k}: list ({len(v)} items)')
            elif isinstance(v, str):
                lines.append(f'{indent}{k}: str (len={len(v)})')
            else:
                lines.append(f'{indent}{k}: {type(v).__name__} = {truncate(str(v), 50)}')
    return lines


def scan_jsonl(filepath: Path) -> str:
    combo_counts = Counter()
    combo_keys = defaultdict(set)
    combo_examples = {}
    combo_tool_names = defaultdict(set)
    combo_nested = {}
    string_content_examples = {}
    string_content_counts = Counter()

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
            message = msg.get('message', {})
            content = message.get('content', None)

            if content is None:
                continue

            if isinstance(content, str):
                combo = f'{msg_type}/string'
                string_content_counts[combo] += 1
                if combo not in string_content_examples:
                    string_content_examples[combo] = content
                continue

            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get('type', 'MISSING')
                combo = f'{msg_type}/{block_type}'
                combo_counts[combo] += 1
                combo_keys[combo].update(block.keys())

                if 'name' in block and block_type == 'tool_use':
                    combo_tool_names[combo].add(block['name'])

                if combo not in combo_examples:
                    combo_examples[combo] = block

                if combo not in combo_nested:
                    combo_nested[combo] = describe_nested(block, max_depth=3)

                # Check tool_result for nested content
                if block_type == 'tool_result':
                    result_content = block.get('content', '')
                    if isinstance(result_content, list):
                        for sub in result_content:
                            if isinstance(sub, dict):
                                sub_type = sub.get('type', '?')
                                sub_combo = f'{combo}/sub:{sub_type}'
                                combo_counts[sub_combo] += 1
                                combo_keys[sub_combo].update(sub.keys())
                                if sub_combo not in combo_examples:
                                    combo_examples[sub_combo] = sub

    lines = []
    lines.append(f'# JSONL Content Block Types')
    lines.append(f'')
    lines.append(f'**Source:** `{filepath.name}` ({filepath.stat().st_size:,} bytes)')
    lines.append(f'**Scanned:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'')

    # Summary table
    lines.append(f'## Summary')
    lines.append(f'')
    lines.append(f'| Combination | Count | Keys |')
    lines.append(f'|-------------|-------|------|')
    for combo, count in combo_counts.most_common():
        keys = ', '.join(sorted(combo_keys[combo]))
        lines.append(f'| `{combo}` | {count} | {keys} |')
    lines.append(f'')

    if string_content_counts:
        lines.append(f'## String Content (non-list)')
        lines.append(f'')
        for combo, count in string_content_counts.most_common():
            lines.append(f'### `{combo}` ({count}x)')
            lines.append(f'')
            example = string_content_examples[combo]
            lines.append(f'**Example:**')
            lines.append(f'```')
            lines.append(truncate(example, 500))
            lines.append(f'```')
            lines.append(f'')

    # Detailed sections
    for combo, count in combo_counts.most_common():
        if '/sub:' in combo:
            continue
        lines.append(f'## `{combo}` ({count}x)')
        lines.append(f'')
        lines.append(f'**Keys:** `{"`, `".join(sorted(combo_keys[combo]))}`')
        lines.append(f'')

        if combo in combo_tool_names and combo_tool_names[combo]:
            tool_list = sorted(combo_tool_names[combo])
            lines.append(f'**Tool names ({len(tool_list)}):** {", ".join(f"`{t}`" for t in tool_list)}')
            lines.append(f'')

        if combo in combo_nested:
            lines.append(f'**Nested structure:**')
            lines.append(f'```')
            for nl in combo_nested[combo]:
                lines.append(nl)
            lines.append(f'```')
            lines.append(f'')

        if combo in combo_examples:
            example = combo_examples[combo]
            lines.append(f'**Example (truncated):**')
            lines.append(f'```json')
            ex_clean = {}
            for k, v in example.items():
                if isinstance(v, str) and len(v) > 300:
                    ex_clean[k] = truncate(v)
                elif isinstance(v, (dict, list)):
                    ex_clean[k] = truncate(json.dumps(v, ensure_ascii=False), 300)
                else:
                    ex_clean[k] = v
            lines.append(json.dumps(ex_clean, indent=2, ensure_ascii=False))
            lines.append(f'```')
            lines.append(f'')

        # Show sub-blocks if any
        sub_combos = [c for c in combo_counts if c.startswith(f'{combo}/sub:')]
        if sub_combos:
            lines.append(f'**Sub-blocks in content:**')
            lines.append(f'')
            for sub in sub_combos:
                sub_count = combo_counts[sub]
                sub_keys = ', '.join(sorted(combo_keys[sub]))
                lines.append(f'- `{sub}` ({sub_count}x) — keys: {sub_keys}')
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
    output_path = REPORTS_DIR / f'content_blocks_{timestamp}.md'
    output_path.write_text(report, encoding='utf-8')
    print(f'Report written to: {output_path}')


if __name__ == '__main__':
    main()
