#!/usr/bin/env python3
# INFRASTRUCTURE
import sys
import argparse
from pathlib import Path

from cache_timeline_parse import parse_session_turns, find_project_sessions
from cache_timeline_analysis import detect_anomalies
from cache_timeline_render import format_turn_table, format_summary, format_minute_chart, format_project_summary


# ORCHESTRATOR

def main():
    args = parse_args()
    if args.session:
        session_path = Path(args.session)
        turns = parse_session_turns(session_path)
        if args.aggregate:
            output = run_aggregate_view(session_path, turns)
        else:
            output = run_timeline_view(session_path, turns, anomalies_only=args.anomalies_only)
    elif args.project:
        output = run_project_view(args.project, include_workers=args.workers)
    else:
        print('Error: --session or --project required', file=sys.stderr)
        sys.exit(1)
    print(output)


# FUNCTIONS

def parse_args():
    parser = argparse.ArgumentParser(description='Analyze cache/token behavior over time in Claude Code sessions')
    parser.add_argument('--session', help='Path to session JSONL file')
    parser.add_argument('--project', help='Project path (absolute) — summary per session')
    parser.add_argument('--aggregate', action='store_true', help='Per-minute aggregation view (requires --session)')
    parser.add_argument('--workers', action='store_true', help='Include worker sessions (requires --project)')
    parser.add_argument('--anomalies-only', action='store_true', dest='anomalies_only', help='Only show turns with anomalies (requires --session)')
    return parser.parse_args()


def run_aggregate_view(session_path, turns):
    _, anomaly_details = detect_anomalies(turns)
    lines = [f'# Cache Timeline (per-minute) — {session_path.name}\n']
    lines.append(format_minute_chart(turns))
    lines.append('')
    lines.append(format_summary(turns, anomaly_details=anomaly_details))
    return '\n'.join(lines)


def run_timeline_view(session_path, turns, anomalies_only=False):
    flags, anomaly_details = detect_anomalies(turns)
    lines = [f'# Cache Timeline — {session_path.name}\n']
    lines.append(format_turn_table(turns, flags=flags, anomalies_only=anomalies_only))
    lines.append('')
    lines.append(format_summary(turns, anomaly_details=anomaly_details))
    return '\n'.join(lines)


def run_project_view(project_path, include_workers=False):
    sessions = find_project_sessions(project_path, include_workers)
    if not sessions:
        return f'No sessions found for project: {project_path}'
    lines = [f'# Cache Timeline — {project_path}\n']
    lines.append(format_project_summary(sessions))
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
