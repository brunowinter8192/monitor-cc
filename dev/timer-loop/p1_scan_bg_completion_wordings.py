# INFRASTRUCTURE
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bg_completion_scan import EXCLUDED_FILES, _scan_file
from bg_completion_report import _build_report

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
DEFAULT_LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'
INITIAL_TOTAL_REQUESTS = 0
INITIAL_TOTAL_PARSE_ERRORS = 0


# ORCHESTRATOR

def main():
    log_dir = compute_log_dir()
    corpus_files = compute_corpus_files(log_dir)
    findings = {}
    cmd_variant_counts = {}
    raw_dup_counter = defaultdict(int)
    bare_hits = defaultdict(int)
    session_is_worker = {}
    total_requests = INITIAL_TOTAL_REQUESTS
    total_parse_errors = INITIAL_TOTAL_PARSE_ERRORS
    total_requests, total_parse_errors = collect_total_requests(corpus_files, findings, cmd_variant_counts, raw_dup_counter, bare_hits, session_is_worker, total_requests, total_parse_errors)
    report = _build_report(findings, cmd_variant_counts, total_requests, total_parse_errors,
                            raw_dup_counter, bare_hits, corpus_files, session_is_worker)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = compute_out_path()
    out_path.write_text(report, encoding='utf-8')
    print_wrote(out_path, findings, total_requests, total_parse_errors)


# FUNCTIONS

def compute_log_dir():
    return Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG_DIR


def compute_corpus_files(log_dir):
    return (sorted(
            p for p in log_dir.glob('*_original.jsonl')
            if p.name not in EXCLUDED_FILES
        ))


def collect_total_requests(corpus_files, findings, cmd_variant_counts, raw_dup_counter, bare_hits, session_is_worker, total_requests, total_parse_errors):
    for path in corpus_files:
        print(f'scanning {path.name} ...')
        requests, parse_errors = _scan_file(
            path, findings, cmd_variant_counts, raw_dup_counter, bare_hits, session_is_worker)
        total_requests += requests
        total_parse_errors += parse_errors
    return total_requests, total_parse_errors


def compute_out_path():
    return REPORT_DIR / 'bg_completion_wordings_20260806.md'


def print_wrote(out_path, findings, total_requests, total_parse_errors):
    print(f'wrote {out_path} — {len(findings)} distinct wording(s), {total_requests} requests scanned, {total_parse_errors} parse errors')


if __name__ == '__main__':
    main()
