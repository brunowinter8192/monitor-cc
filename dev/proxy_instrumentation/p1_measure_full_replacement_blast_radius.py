# INFRASTRUCTURE
from pathlib import Path

from blast_radius_engine import _scan_file
from blast_radius_report import _build_report

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'

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
INITIAL_TOTAL_REQUESTS = 0


# ORCHESTRATOR

def main():
    records = []
    total_requests = INITIAL_TOTAL_REQUESTS
    total_requests = collect_total_requests(total_requests, records)
    report = _build_report(records, total_requests, CORPUS_FILES, EXCLUDED_FILES)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = compute_out_path()
    out_path.write_text(report, encoding='utf-8')
    print_wrote(out_path, records, total_requests)


# FUNCTIONS


def collect_total_requests(total_requests, records):
    for fname in CORPUS_FILES:
        path = LOG_DIR / fname
        print(f'scanning {fname} ...')
        total_requests += _scan_file(path, records)
    return total_requests


def compute_out_path():
    return REPORT_DIR / 'full_replacement_blast_radius_20260729.md'


def print_wrote(out_path, records, total_requests):
    print(f'wrote {out_path} — {len(records)} ops captured, {total_requests} requests scanned')


if __name__ == '__main__':
    main()
