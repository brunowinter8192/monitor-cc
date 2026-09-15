"""
main_log_elimination_probe.py — Feasibility probe for eliminating the main log.

Answers two questions on a real session:

  Question A (Forwarded reconstruction):
    Accumulate _forwarded delta log into a full forwarded payload per request.
    Diff against main log raw_payload (pre-cache-ops) after normalising cache_control.
    Report content match, BP-count divergence, and missing top-level fields.

  Question B (Error extraction):
    Extract is_error==True tool_result blocks from _original payloads.
    Dedup by tool_use_id. Compare against tool_errors.jsonl for this session.

Session data:
  Main log:     src/logs/api_requests_<session>.jsonl
  Quartet:      src/logs/dual_log/api_requests_<session>_{original,forwarded,...}.jsonl
  Tool errors:  src/logs/tool_errors.jsonl

Matching strategy: positional — entry N in _forwarded == request entry N in main log.
Both are written by the same serial proxy request() hook in identical order.
Request IDs are empty in quartet (CC sends no x-request-id header); main log uses UUID4.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe.py <session_suffix>

    <session_suffix> is the log_id portion, e.g. opus_monitor_cc_1780602018

    Paths are resolved relative to the project root (MONITOR_CC_ROOT or auto-detected).
"""

# INFRASTRUCTURE
import argparse

from main_log_elimination_io import (
    _resolve_root, _resolve_paths, _check_paths, _load_jsonl, _load_main_log, _load_tool_errors,
)
from main_log_elimination_questions import _run_question_a, _run_question_b
from main_log_elimination_report import _write_report

# ORCHESTRATOR

def main_log_elimination_probe_workflow(session: str) -> None:
    root = _resolve_root()
    paths = _resolve_paths(root, session)
    _check_paths(paths)

    main_entries = _load_main_log(paths["main"])
    fwd_entries = _load_jsonl(paths["fwd"])
    orig_entries = _load_jsonl(paths["orig"])
    tool_errors = _load_tool_errors(paths["tool_errors"], session)

    a_results = _run_question_a(main_entries, fwd_entries)
    b_results = _run_question_b(orig_entries, tool_errors)

    report_path = _write_report(session, paths, a_results, b_results)
    print(report_path)

# FUNCTIONS

# Resolve log file path from session suffix
def _cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe: can _forwarded quartet replace the main log?"
    )
    parser.add_argument(
        "session",
        nargs="?",
        default="opus_monitor_cc_1780602018",
        help="Log session suffix, e.g. opus_monitor_cc_1780602018",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _cli()
    main_log_elimination_probe_workflow(args.session)
