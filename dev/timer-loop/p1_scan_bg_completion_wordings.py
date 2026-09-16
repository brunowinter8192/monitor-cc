"""
Milestone 1 — inventory distinct CC background-task COMPLETION/kill notice wordings in the
real recorded corpus, for main (orchestrator) vs worker sessions.

Measurement only: scans src/logs/dual_log/*_original.jsonl for messages that look like a CC
background-task completion notice (the <task-notification> family) or a bare "Background
command "..." completed/failed" notice (the strip_bg_completed.py family), dedups cumulative
dual-log duplication, buckets by (status, exit-code, normalized summary template), and
evaluates the real id-extraction mechanism (payload_helpers._extract_task_notification_task_id)
against each wording. Writes report to dev/timer-loop/md/.

Companion to dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py (launch side); this covers
the completion side.

Usage (from project root or worktree root):
    ./venv/bin/python dev/timer-loop/p1_scan_bg_completion_wordings.py [log_dir]
"""

# INFRASTRUCTURE
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bg_completion_scan import EXCLUDED_FILES, _scan_file
from bg_completion_report import _build_report

# Corpus dir: parameterized, defaults to the main checkout's dual-log dir (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
DEFAULT_LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'


# ORCHESTRATOR
def main():
    log_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG_DIR
    corpus_files = sorted(
        p for p in log_dir.glob('*_original.jsonl')
        if p.name not in EXCLUDED_FILES
    )
    findings = {}
    cmd_variant_counts = {}
    raw_dup_counter = defaultdict(int)
    bare_hits = defaultdict(int)
    session_is_worker = {}
    total_requests = 0
    total_parse_errors = 0
    for path in corpus_files:
        print(f'scanning {path.name} ...')
        requests, parse_errors = _scan_file(
            path, findings, cmd_variant_counts, raw_dup_counter, bare_hits, session_is_worker)
        total_requests += requests
        total_parse_errors += parse_errors
    report = _build_report(findings, cmd_variant_counts, total_requests, total_parse_errors,
                            raw_dup_counter, bare_hits, corpus_files, session_is_worker)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / 'bg_completion_wordings_20260806.md'
    out_path.write_text(report, encoding='utf-8')
    print(f'wrote {out_path} — {len(findings)} distinct wording(s), {total_requests} requests scanned, {total_parse_errors} parse errors')


if __name__ == '__main__':
    main()
