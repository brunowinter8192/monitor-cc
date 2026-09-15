#!/usr/bin/env python3
# INFRASTRUCTURE
import sys
import argparse
from pathlib import Path

from cache_rebuild_context_parse import find_all_sessions, parse_all_messages
from cache_rebuild_context_detect import detect_rebuilds
from cache_rebuild_context_render import (
    format_rebuild_block, format_pattern_summary, format_delta_summary, format_session_rebuild_table,
)

DEFAULT_CONTEXT = 5

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.all:
        output = run_all(args.context)
    elif args.session:
        output = run_session(Path(args.session), args.context, args.summary_only)
    else:
        print('Error: --session or --all required', file=sys.stderr)
        sys.exit(1)
    print(output)

def run_session(session_path, context_window, summary_only):
    messages = parse_all_messages(session_path)
    rebuilds = detect_rebuilds(messages)
    lines = [f'# Cache Rebuild Context — {session_path.name}\n']
    if not rebuilds:
        lines.append('_No cache rebuilds detected._')
        return '\n'.join(lines)
    if not summary_only:
        for i, rebuild in enumerate(rebuilds, 1):
            lines.append(format_rebuild_block(rebuild, messages, i, context_window))
            lines.append('')
    lines.append(format_pattern_summary(rebuilds))
    lines.append(format_delta_summary(rebuilds))
    return '\n'.join(lines)

def run_all(context_window):
    sessions = find_all_sessions()
    lines = ['# Cache Rebuild Context — All Projects\n']
    all_rebuilds = []
    session_rows = []
    for session_path in sessions:
        messages = parse_all_messages(session_path)
        rebuilds = detect_rebuilds(messages)
        if rebuilds:
            all_rebuilds.extend(rebuilds)
            session_rows.append((session_path, len(rebuilds)))
    lines.append(format_session_rebuild_table(session_rows))
    lines.append('')
    lines.append(format_pattern_summary(all_rebuilds))
    lines.append(format_delta_summary(all_rebuilds))
    return '\n'.join(lines)

# FUNCTIONS

def parse_args():
    parser = argparse.ArgumentParser(description='Analyze cache rebuilds in Claude Code sessions')
    parser.add_argument('--session', help='Path to session JSONL file')
    parser.add_argument('--context', type=int, default=DEFAULT_CONTEXT,
                        help=f'Messages before/after rebuild (default: {DEFAULT_CONTEXT})')
    parser.add_argument('--summary-only', action='store_true', dest='summary_only',
                        help='Show only pattern summary, no context blocks')
    parser.add_argument('--all', action='store_true',
                        help='Scan all session JSONLs across all projects')
    return parser.parse_args()


if __name__ == '__main__':
    main()
