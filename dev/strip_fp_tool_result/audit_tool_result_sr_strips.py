#!/usr/bin/env python3

# INFRASTRUCTURE
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
