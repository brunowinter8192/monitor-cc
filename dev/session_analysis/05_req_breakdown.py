#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
from datetime import datetime
from pathlib import Path

from req_breakdown_load import load_proxy_entry, load_session_ground_truth, tokenize_segments
from req_breakdown_attribution import compute_prefix_attribution
from req_breakdown_rule_edits import compute_rule_edits
from req_breakdown_report import build_report

REPORTS_DIR = Path(__file__).parent / "04_reports"
INITIAL_ATTRIBUTION = None


# ORCHESTRATOR

def main():
    args = parse_args()
    proxy_path = Path(args.proxy_log)
    session_path = Path(args.session_jsonl).expanduser()
    prev_proxy_path = compute_prev_proxy_path(args)
    req_n = args.req

    target_entry = load_proxy_entry(proxy_path, req_n)
    cr, cc, d, out = load_session_ground_truth(session_path, req_n)
    sys_rows, tools_rows, msg_rows, estimate = tokenize_segments(target_entry)

    attribution = INITIAL_ATTRIBUTION
    if prev_proxy_path and cr > 0:
        attribution = compute_prefix_attribution(target_entry, prev_proxy_path, cr, cc)

    rule_edits = compute_rule_edits(proxy_path, prev_proxy_path, attribution)
    report = build_report(
        req_n, proxy_path, session_path, cr, cc, d, out,
        sys_rows, tools_rows, msg_rows, estimate, attribution, rule_edits,
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = compute_report_path(ts, req_n)
    report_path.write_text(report)
    print_report(report_path)


# FUNCTIONS

def parse_args():
    parser = argparse.ArgumentParser(description='Forensic breakdown of proxy API request token attribution')
    parser.add_argument('--proxy-log', required=True, help='Proxy JSONL log file')
    parser.add_argument('--session-jsonl', required=True, help='Session JSONL file')
    parser.add_argument('--req', type=int, default=1, help='Request number 1-based, opus only (default: 1)')
    parser.add_argument('--prev-proxy-log', help='Previous session proxy log for prefix byte-diff attribution')
    return parser.parse_args()


def compute_prev_proxy_path(args):
    return Path(args.prev_proxy_log).expanduser() if args.prev_proxy_log else None


def compute_report_path(ts, req_n):
    return REPORTS_DIR / f"{ts}_req{req_n}.md"


def print_report(report_path):
    print(f"Report: {report_path}")


if __name__ == '__main__':
    main()
