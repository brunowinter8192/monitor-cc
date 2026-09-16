# INFRASTRUCTURE
import os
from datetime import datetime, timezone

from error_cluster_extraction import load_entries, cluster_entries
from error_cluster_crosscheck import run_cross_check
from error_cluster_report import format_report, write_report

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPORT_DATE  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MAIN_PROJECT = None  # resolved below


# Resolve MAIN_PROJECT at import time via .git file traversal (worktree-aware)
def _resolve_main_project() -> str:
    p = SCRIPT_DIR
    while p != os.path.dirname(p):
        git = os.path.join(p, ".git")
        if os.path.isfile(git):
            content = open(git).read().strip()
            if content.startswith("gitdir:"):
                gitdir = content[len("gitdir:"):].strip()
                return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))
        elif os.path.isdir(git):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("Cannot find main project root")


MAIN_PROJECT = _resolve_main_project()
LOGS_DIR     = os.path.join(MAIN_PROJECT, "src", "logs")
REPORTS_DIR  = os.path.join(SCRIPT_DIR, "reports")

TOOL_ERRORS_LOG = os.path.join(LOGS_DIR, "tool_errors.jsonl")


# ORCHESTRATOR

# Load tool_errors.jsonl → cluster → classify → cross-check via proxy logs → write report
def audit_workflow() -> None:
    entries        = load_entries(TOOL_ERRORS_LOG)
    buckets        = cluster_entries(entries)
    cross_check    = run_cross_check(buckets, LOGS_DIR)
    report         = format_report(entries, buckets, cross_check, REPORT_DATE)
    path           = write_report(report, REPORTS_DIR, REPORT_DATE)
    print(path)


if __name__ == "__main__":
    audit_workflow()
