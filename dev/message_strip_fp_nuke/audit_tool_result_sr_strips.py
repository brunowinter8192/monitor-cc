#!/usr/bin/env python3

# INFRASTRUCTURE
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dev.refactoring.live_log_isolation import isolate_monitor_root

_ROOT_SANDBOX = isolate_monitor_root("audit_tool_result_sr_")

from audit_report import _render_report, _write_report
from audit_scan import _discover_corpus_files, _scan_files, _scan_ground_truth_git_lock


# ORCHESTRATOR

def main():
    included, excluded = _discover_corpus_files()
    per_file_stats, occurrences, assertion_hits = _scan_files(included)
    ground_truth = _scan_ground_truth_git_lock(included)
    report = _render_report(included, excluded, per_file_stats, occurrences, assertion_hits, ground_truth)
    _write_report(report)


if __name__ == '__main__':
    main()
