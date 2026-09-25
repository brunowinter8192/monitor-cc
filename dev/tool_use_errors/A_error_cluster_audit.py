# INFRASTRUCTURE
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dev.refactoring.repo_roots import resolve_main_project
from error_cluster_extraction import load_entries, cluster_entries
from error_cluster_crosscheck import run_cross_check
from error_cluster_report import format_report, write_report

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPORT_DATE  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MAIN_PROJECT = None

MAIN_PROJECT = resolve_main_project(SCRIPT_DIR)
LOGS_DIR     = os.path.join(MAIN_PROJECT, "src", "logs")
REPORTS_DIR  = os.path.join(SCRIPT_DIR, "reports")

TOOL_ERRORS_LOG = os.path.join(LOGS_DIR, "tool_errors.jsonl")


# ORCHESTRATOR

def audit_workflow() -> None:
    entries        = load_entries(TOOL_ERRORS_LOG)
    buckets        = cluster_entries(entries)
    cross_check    = run_cross_check(buckets, LOGS_DIR)
    report         = format_report(entries, buckets, cross_check, REPORT_DATE)
    path           = write_report(report, REPORTS_DIR, REPORT_DATE)
    print(path)


if __name__ == "__main__":
    audit_workflow()
