#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
from datetime import datetime
from pathlib import Path

from quartet_prefix_diff_load import (
    load_ground_truth, load_forwarded_opus_states, map_requests_to_fwd_states,
    detect_cr_collapse_points, build_range_pairs, pair_available,
    collect_target_flow_ids, load_original_payloads,
)
from quartet_prefix_diff_diff import analyze_pair
from quartet_prefix_diff_report import build_report

REPORTS_DIR = Path(__file__).parent / "md"


# ORCHESTRATOR

def main():
    args = parse_args()
    fwd_path = Path(args.forwarded_log)
    session_path = Path(args.session_jsonl).expanduser()
    original_path = compute_original_path(args)

    ground_truth = load_ground_truth(session_path)
    fwd_states = load_forwarded_opus_states(fwd_path)
    mapped, mapping_notes = map_requests_to_fwd_states(ground_truth, fwd_states)

    collapse_points = detect_cr_collapse_points(mapped)
    range_pairs = compute_range_pairs(args)
    auto_pairs = compute_auto_pairs(collapse_points, args)
    pairs = compute_pairs(range_pairs, auto_pairs)
    pairs = compute_pairs_2(pairs, mapped)

    orig_by_flow = None
    if original_path:
        target_flow_ids = collect_target_flow_ids(mapped, pairs)
        orig_by_flow = load_original_payloads(original_path, target_flow_ids)

    pair_results = compute_pair_results(mapped, orig_by_flow, pairs)

    report = build_report(
        fwd_path, session_path, original_path, ground_truth, mapped, mapping_notes,
        collapse_points, range_pairs, auto_pairs, pair_results,
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = compute_report_path(ts)
    report_path.write_text(report)
    print(f"Report: {report_path}")


# FUNCTIONS

def parse_args():
    parser = argparse.ArgumentParser(description="Forensic per-segment prefix-diff for cache rebuilds")
    parser.add_argument("--forwarded-log", required=True, help="_forwarded dual-log JSONL (delta-encoded)")
    parser.add_argument("--session-jsonl", required=True, help="Session JSONL for ground-truth CR/CC/D")
    parser.add_argument("--req-range", help="Consecutive REQ pair range to analyze, e.g. 133-137")
    parser.add_argument("--auto-detect", action="store_true", help="Also scan the whole log for CR-collapse points")
    parser.add_argument("--original-log", help="_original dual-log JSONL (full non-delta incoming payloads) "
                                                "for client-side-vs-proxy-side attribution of message diffs")
    return parser.parse_args()


def compute_original_path(args):
    return Path(args.original_log).expanduser() if args.original_log else None


def compute_range_pairs(args):
    return build_range_pairs(args.req_range) if args.req_range else []


def compute_auto_pairs(collapse_points, args):
    return [(c - 1, c) for c in collapse_points] if args.auto_detect else []


def compute_pairs(range_pairs, auto_pairs):
    return sorted(set(range_pairs) | set(auto_pairs))


def compute_pairs_2(pairs, mapped):
    return [(p1, p2) for p1, p2 in pairs if pair_available(mapped, p1, p2)]


def compute_pair_results(mapped, orig_by_flow, pairs):
    return [analyze_pair(mapped, p1, p2, orig_by_flow) for p1, p2 in pairs]


def compute_report_path(ts):
    return REPORTS_DIR / f"{ts}_quartet_prefix_diff.md"


if __name__ == "__main__":
    main()
