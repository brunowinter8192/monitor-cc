"""
D2 — blast-radius measurement for a full-replacement-aware _extract_block_op.

Measurement only: drives real recorded payloads through the real message-pass functions
(src/proxy/message_passes.py) in src/proxy/rules.py::apply_modification_rules's actual
pass order, capturing every (offset, removed, injected) op _ops_from_content_change
produces, per pass. Classifies each op's SITE semantically (by reading the underlying
strip function: does it construct new block content INDEPENDENTLY of the old — a whole-
content replacement — or does it EXCISE a known chunk from within surrounding text and
keep the remainder?) — not by any len(removed)/len(bt) threshold. The ratio is reported
only as corroborating evidence, never as the classifier. Writes report to
dev/proxy_instrumentation/md/.

Usage (from project root or worktree root):
    ./venv/bin/python dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py
"""

# INFRASTRUCTURE
from pathlib import Path

from blast_radius_engine import _scan_file
from blast_radius_report import _build_report

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'

# Same corpus + exclusion rationale as D1 (dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py)
CORPUS_FILES = [
    'api_requests_opus_monitor_cc_1785336796_original.jsonl',
    'api_requests_opus_posts_1785338463_original.jsonl',
    'api_requests_opus_wise2627_1785324012_original.jsonl',
    'api_requests_worker_25c51a2e_tn-role-system_1785344818_original.jsonl',
]
EXCLUDED_FILES = {
    'api_requests_opus_monitor_cc_1785347492_original.jsonl':
        'currently-live session (see D1 report for timestamps)',
    'api_requests_worker_25c51a2e_bg-ack-shapes_1785359201_original.jsonl':
        "this worker's own worktree activity",
}


# ORCHESTRATOR
def main():
    records = []
    total_requests = 0
    for fname in CORPUS_FILES:
        path = LOG_DIR / fname
        print(f'scanning {fname} ...')
        total_requests += _scan_file(path, records)
    report = _build_report(records, total_requests, CORPUS_FILES, EXCLUDED_FILES)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / 'full_replacement_blast_radius_20260729.md'
    out_path.write_text(report, encoding='utf-8')
    print(f'wrote {out_path} — {len(records)} ops captured, {total_requests} requests scanned')


if __name__ == '__main__':
    main()
