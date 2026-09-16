#!/usr/bin/env python3
# INFRASTRUCTURE
from char_token_ratio_load import (
    find_latest_proxy_log, find_latest_session_jsonl, load_proxy_rows, load_session_events, pair_rows,
)
from char_token_ratio_compute import compute_ratios, compute_tiktoken_drift
from char_token_ratio_report import build_report, write_report

# ORCHESTRATOR

def main():
    proxy_path = find_latest_proxy_log()
    session_path = find_latest_session_jsonl()
    print(f"Proxy log:    {proxy_path}")
    print(f"Session JSONL: {session_path}")

    proxy_rows = load_proxy_rows(proxy_path)
    session_events = load_session_events(session_path)
    paired = pair_rows(proxy_rows, session_events)

    msg_ratios, prefix_ratio, prefix_info = compute_ratios(paired)
    tiktoken_drift = compute_tiktoken_drift(proxy_path, paired)

    report = build_report(paired, msg_ratios, prefix_ratio, prefix_info, tiktoken_drift, proxy_path, session_path)
    report_path = write_report(report)
    print(report)
    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
