# INFRASTRUCTURE
import argparse
import sys
from datetime import datetime
from pathlib import Path

from rag_truncation_audit_data import (
    _load_proxy, _source_label, _collect_tool_uses, _collect_truncated_results,
    _collect_echo_hits, _classify,
)
from rag_truncation_audit_report import _build_report


# ORCHESTRATOR

def run(jsonl_paths, output_path):
    per_source_events = {}
    all_events = []
    for path in jsonl_paths:
        label = _source_label(path)
        evs = _load_proxy(path)
        per_source_events[label] = evs
        all_events.extend(evs)

    tool_uses            = _collect_tool_uses(all_events)
    trunc_results        = _collect_truncated_results(all_events)
    echo_hits            = _collect_echo_hits(all_events)
    classified           = _classify(trunc_results, tool_uses)
    report               = _build_report(jsonl_paths, per_source_events, tool_uses,
                                         trunc_results, echo_hits, classified)
    _write_output(report, output_path)


# FUNCTIONS

def _write_output(report, path):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(path)
    else:
        sys.stdout.write(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Classify [N characters truncated] occurrences in Opus proxy logs.'
    )
    parser.add_argument(
        'proxy_jsonl', nargs='*',
        help='Proxy JSONL path(s). Default: all src/logs/api_requests_opus_monitor_cc_*.jsonl'
    )
    parser.add_argument('--output', default='', help='Output markdown file (default: auto-dated)')
    args = parser.parse_args()

    if args.proxy_jsonl:
        paths = args.proxy_jsonl
    else:
        import glob
        root  = Path(__file__).parent.parent.parent
        paths = sorted(glob.glob(str(root / 'src/logs/api_requests_opus_monitor_cc_*.jsonl')))
        if not paths:
            print('No proxy logs found under src/logs/', file=sys.stderr)
            sys.exit(1)

    if args.output:
        out = args.output
    else:
        date = datetime.now().strftime('%Y%m%d')
        out  = str(Path(__file__).parent / f'{date}_rag_truncation_audit.md')

    run(paths, out)
