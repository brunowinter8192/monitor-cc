#!/usr/bin/env python3
"""Extract zero-result Grep/Glob/Read tool calls from Claude Code session JSONL files."""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from datetime import datetime

TARGET_TOOLS = ('Grep', 'Glob', 'Read')
ZERO_PATTERNS = {
    'Grep': ['No matches found', 'No files found'],
    'Glob': ['No files found'],
    'Read': ['File does not exist', 'does not exist'],
}
MAX_PRECEDING_CHARS = 400


# ORCHESTRATOR

def extract_zeros_workflow(session_paths, output_path):
    all_zeros = []
    session_summaries = []
    for path in session_paths:
        events = load_events(path)
        uuid_map = build_uuid_map(events)
        tool_uses = collect_tool_uses(events)
        zeros = find_zero_results(events, tool_uses, uuid_map, path)
        all_zeros.extend(zeros)
        session_summaries.append({
            'path': path,
            'session_id': extract_session_id(path),
            'total': len(zeros),
            'counts': count_by_tool(zeros),
        })
    report = build_report(session_paths, session_summaries, all_zeros)
    write_output(report, output_path)


# FUNCTIONS

def load_events(path):
    """Load and parse all JSON events from a session JSONL file."""
    events = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def build_uuid_map(events):
    """Build uuid -> event index map for parent-chain traversal."""
    uuid_map = {}
    for i, e in enumerate(events):
        uid = e.get('uuid')
        if uid:
            uuid_map[uid] = i
    return uuid_map


def collect_tool_uses(events):
    """Collect Grep/Glob/Read tool_use blocks indexed by tool_use_id."""
    tool_uses = {}
    for i, e in enumerate(events):
        if e.get('type') != 'assistant':
            continue
        content = e.get('message', {}).get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use' and block.get('name') in TARGET_TOOLS:
                tool_uses[block['id']] = (i, block, e)
    return tool_uses


def find_zero_results(events, tool_uses, uuid_map, session_path):
    """Match tool_result events to tool_uses and return zero-result entries."""
    zeros = []
    session_id = extract_session_id(session_path)
    for e in events:
        if e.get('type') != 'user':
            continue
        content = e.get('message', {}).get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get('type') != 'tool_result':
                continue
            tid = block.get('tool_use_id')
            if tid not in tool_uses:
                continue
            result_text = extract_result_text(block)
            _, tblock, ass_event = tool_uses[tid]
            tool_name = tblock.get('name', '')
            if not is_zero_result(tool_name, result_text):
                continue
            preceding = get_preceding_text(ass_event, uuid_map, events)
            ts = ass_event.get('timestamp', '')
            zeros.append({
                'session_id': session_id,
                'session_path': session_path,
                'timestamp': ts,
                'timestamp_local': format_timestamp_local(ts),
                'tool_name': tool_name,
                'input': tblock.get('input', {}),
                'result': result_text,
                'preceding': preceding,
            })
    return zeros


def is_zero_result(tool_name, result_text):
    """Return True if result_text indicates a zero-result for the given tool.

    Read guard: successful reads always start with a line-number prefix (digit+tab).
    If result starts with that prefix, it is real file content — not a zero-result.
    """
    if tool_name not in ZERO_PATTERNS:
        return False
    if tool_name == 'Read' and re.match(r'^\d+\t', result_text):
        return False
    for pat in ZERO_PATTERNS[tool_name]:
        if pat.lower() in result_text.lower():
            return True
    return False


def extract_result_text(result_block):
    """Extract plain text from a tool_result block (handles str and list content)."""
    content = result_block.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get('text', ''))
            elif isinstance(item, str):
                parts.append(item)
        return ' '.join(parts)
    return ''


def get_preceding_text(event, uuid_map, events):
    """Walk up parentUuid chain from event, return first text block found."""
    visited = set()
    cur_uuid = event.get('parentUuid')
    while cur_uuid and cur_uuid not in visited:
        visited.add(cur_uuid)
        idx = uuid_map.get(cur_uuid)
        if idx is None:
            break
        e = events[idx]
        if e.get('type') == 'assistant':
            content = e.get('message', {}).get('content', [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        txt = block.get('text', '').strip()
                        if txt:
                            return txt[:MAX_PRECEDING_CHARS]
        cur_uuid = e.get('parentUuid')
    return None


def extract_session_id(path):
    """Extract session UUID from file path (stem of the .jsonl filename)."""
    return os.path.splitext(os.path.basename(path))[0]


def format_timestamp_local(ts_str):
    """Convert UTC ISO timestamp string to local HH:MM:SS."""
    if not ts_str:
        return '?'
    try:
        dt_utc = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt_utc.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]


def count_by_tool(zeros):
    """Return dict of tool_name -> count."""
    counts = {}
    for z in zeros:
        t = z['tool_name']
        counts[t] = counts.get(t, 0) + 1
    return counts


def format_input_params(tool_name, input_dict):
    """Format tool input parameters as markdown lines for the report."""
    lines = []
    if tool_name == 'Grep':
        if 'pattern' in input_dict:
            lines.append(f'**Pattern:** `{input_dict["pattern"]}`')
        if 'path' in input_dict:
            lines.append(f'**Path:** `{input_dict["path"]}`')
        if 'glob' in input_dict:
            lines.append(f'**Glob filter:** `{input_dict["glob"]}`')
        if 'output_mode' in input_dict:
            lines.append(f'**Output mode:** {input_dict["output_mode"]}')
        if 'type' in input_dict:
            lines.append(f'**File type:** {input_dict["type"]}')
    elif tool_name == 'Glob':
        if 'pattern' in input_dict:
            lines.append(f'**Pattern:** `{input_dict["pattern"]}`')
        if 'path' in input_dict:
            lines.append(f'**Path:** `{input_dict["path"]}`')
    elif tool_name == 'Read':
        if 'file_path' in input_dict:
            lines.append(f'**File:** `{input_dict["file_path"]}`')
        if 'offset' in input_dict:
            lines.append(f'**Offset:** {input_dict["offset"]}')
        if 'limit' in input_dict:
            lines.append(f'**Limit:** {input_dict["limit"]}')
    if not lines:
        lines.append(f'**Input:** `{json.dumps(input_dict)}`')
    return '\n'.join(lines)


def build_report(session_paths, session_summaries, all_zeros):
    """Build the full markdown report."""
    lines = []
    multi = len(session_paths) > 1

    # Header
    if multi:
        lines.append('# Zero-Result Tool Calls')
    else:
        sid = extract_session_id(session_paths[0])
        lines.append(f'# Zero-Result Tool Calls — {sid}')
    lines.append('')

    if multi:
        lines.append(f'**Sessions analyzed:** {len(session_paths)}')

    total_all = sum(s['total'] for s in session_summaries)
    all_counts = {}
    for s in session_summaries:
        for t, c in s['counts'].items():
            all_counts[t] = all_counts.get(t, 0) + c
    counts_str = ', '.join(
        f'{t}={all_counts.get(t, 0)}' for t in ('Grep', 'Glob', 'Read')
    )
    lines.append(f'**Total zero-results:** {total_all} ({counts_str})')
    lines.append('')

    if multi:
        lines.append('### Per-Session Summary')
        lines.append('')
        lines.append('| Session | Grep | Glob | Read | Total |')
        lines.append('|---------|------|------|------|-------|')
        for s in session_summaries:
            sid = s['session_id'][:12]
            grep_c = s['counts'].get('Grep', 0)
            glob_c = s['counts'].get('Glob', 0)
            read_c = s['counts'].get('Read', 0)
            lines.append(f'| `{sid}` | {grep_c} | {glob_c} | {read_c} | {s["total"]} |')
        lines.append('')
    else:
        lines.append(f'**Session:** `{session_paths[0]}`')
        lines.append('')

    # Note on 146 discrepancy
    lines.append('> **Note on warnings-pane count:** The Monitor_CC warnings pane aggregates')
    lines.append('> zero-results across the full Claude Code process tree (parent session +')
    lines.append('> all worker sub-sessions + any hook calls). A single session JSONL covers')
    lines.append('> only the parent session. To approach the live count, pass all worker')
    lines.append('> session JSONLs as additional arguments.')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Individual entries
    for n, z in enumerate(all_zeros, 1):
        sid = z['session_id']
        ts = z['timestamp_local']
        tool = z['tool_name']

        if multi:
            lines.append(f'## [{n}] {ts} — {tool} — `{sid[:12]}`')
        else:
            lines.append(f'## [{n}] {ts} — {tool}')
        lines.append('')

        lines.append(format_input_params(tool, z['input']))
        lines.append('')

        result_preview = z['result'].strip()
        if len(result_preview) > 120:
            result_preview = result_preview[:120] + '…'
        lines.append(f'**Result:** {result_preview}')
        lines.append('')

        preceding = z.get('preceding')
        if preceding:
            preceding_display = preceding.replace('\n', ' ').strip()
            lines.append('**Context (preceding assistant text):**')
            lines.append(f'> {preceding_display}')
        else:
            lines.append('**Context:** *(no preceding text found)*')
        lines.append('')
        lines.append('---')
        lines.append('')

    return '\n'.join(lines)


def write_output(content, path):
    """Write report to file or stdout."""
    if path:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract zero-result Grep/Glob/Read calls from Claude Code session JSONL files.'
    )
    parser.add_argument(
        'session_jsonl',
        nargs='+',
        help='Path(s) to session JSONL file(s) under ~/.claude/projects/'
    )
    parser.add_argument(
        '--output',
        default=None,
        metavar='FILE',
        help='Output markdown file path (default: stdout)'
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    extract_zeros_workflow(args.session_jsonl, args.output)
