"""Sleep pattern analyzer for block_chained_sleep hook events.

Walks ~/.claude/projects/*/*.jsonl for the last 30 days, correlates each
block_chained_sleep event to its trigger Bash command via tool_use_id, parses
every `sleep N` in that command for context (cmd_before, cmd_after, chain_op,
in_loop, is_canonical), and produces a classification report.

Usage (from project root):
    ./venv/bin/python dev/sleep_pattern_analysis/analyze.py [--since YYYY-MM-DD] [--out PATH]
"""

# INFRASTRUCTURE
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sleep_events import _collect_events
from sleep_parsing import _parse_all_sleeps
from sleep_report import _build_report

DEFAULT_DAYS = 30


# ORCHESTRATOR


def analyze_sleep_patterns_workflow():
    args = _parse_args()
    since_dt = (
        datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if args.since
        else datetime.now(timezone.utc) - timedelta(days=DEFAULT_DAYS)
    )
    events = _collect_events(since_dt)
    records = _parse_all_sleeps(events)
    report = _build_report(records, events, since_dt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(out)


# FUNCTIONS


def _parse_args():
    p = argparse.ArgumentParser(description="Analyze block_chained_sleep events")
    p.add_argument("--since", default=None, help="YYYY-MM-DD (default: 30d ago)")
    p.add_argument("--out", default="dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md")
    return p.parse_args()


if __name__ == "__main__":
    analyze_sleep_patterns_workflow()
