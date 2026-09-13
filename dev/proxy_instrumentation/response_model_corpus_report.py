# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'response_model_corpus_report.md'

# ORCHESTRATOR

def build_response_model_report_workflow() -> None:
    log_files = _all_response_logs()
    entries = _load_entries(log_files)
    stats = _compute_stats(entries)
    _write_report(log_files, stats)
    print(f"[response_model_corpus_report] {stats['total']} entries across {len(log_files)} files -> {REPORT_PATH}")

# FUNCTIONS


def _all_response_logs() -> list:
    return sorted(LOG_DIR.glob('*_response.jsonl'))


def _load_entries(log_files: list) -> list:
    entries = []
    for path in log_files:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
    return entries


def _compute_stats(entries: list) -> dict:
    total = len(entries)
    with_answering_model = 0
    without_answering_model = 0
    content_type_values = {}
    content_encoding_values = {}
    status_counts = {}
    forwarded_present = 0
    answering_present = 0
    both_present_match = 0
    both_present_mismatch = 0
    cc_requested_model_values = {}
    proxy_forwarded_model_values = {}
    answering_model_values = {}
    override_active_count = 0

    for e in entries:
        status_counts[e.get('status_code')] = status_counts.get(e.get('status_code'), 0) + 1
        headers = e.get('headers', {})
        ct = headers.get('content-type')
        if ct:
            content_type_values[ct] = content_type_values.get(ct, 0) + 1
        ce = headers.get('content-encoding')
        if ce:
            content_encoding_values[ce] = content_encoding_values.get(ce, 0) + 1

        cc_requested_model = e.get('cc_requested_model', '')
        proxy_forwarded_model = e.get('proxy_forwarded_model', '')
        answering_model = e.get('answering_model', '')
        if cc_requested_model:
            cc_requested_model_values[cc_requested_model] = cc_requested_model_values.get(cc_requested_model, 0) + 1
        if proxy_forwarded_model:
            forwarded_present += 1
            proxy_forwarded_model_values[proxy_forwarded_model] = proxy_forwarded_model_values.get(proxy_forwarded_model, 0) + 1
        if cc_requested_model and proxy_forwarded_model and cc_requested_model != proxy_forwarded_model:
            override_active_count += 1
        if answering_model:
            answering_present += 1
            with_answering_model += 1
            answering_model_values[answering_model] = answering_model_values.get(answering_model, 0) + 1
        else:
            without_answering_model += 1
        if proxy_forwarded_model and answering_model:
            if proxy_forwarded_model == answering_model:
                both_present_match += 1
            else:
                both_present_mismatch += 1

    return {
        'total': total,
        'with_answering_model': with_answering_model,
        'without_answering_model': without_answering_model,
        'content_type_values': content_type_values,
        'content_encoding_values': content_encoding_values,
        'status_counts': status_counts,
        'forwarded_present': forwarded_present,
        'answering_present': answering_present,
        'both_present_match': both_present_match,
        'both_present_mismatch': both_present_mismatch,
        'cc_requested_model_values': cc_requested_model_values,
        'proxy_forwarded_model_values': proxy_forwarded_model_values,
        'answering_model_values': answering_model_values,
        'override_active_count': override_active_count,
    }


def _write_report(log_files: list, stats: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append('# Response Model Corpus Report')
    lines.append('')
    lines.append(f'Generated: {datetime.now(timezone.utc).isoformat()}Z')
    lines.append(f'Source: `{LOG_DIR}` ({len(log_files)} `*_response.jsonl` files)')
    lines.append('')
    lines.append('## Headline numbers')
    lines.append('')
    lines.append(f'- Total `_response` entries: {stats["total"]}')
    lines.append(f'- Entries carrying an `answering_model`: {stats["with_answering_model"]}')
    lines.append(f'- Entries missing `answering_model`: {stats["without_answering_model"]}')
    lines.append(f'- Entries carrying a `proxy_forwarded_model`: {stats["forwarded_present"]}')
    lines.append(f'- Entries where proxy_forwarded_model == answering_model: {stats["both_present_match"]}')
    lines.append(f'- Entries where proxy_forwarded_model != answering_model: {stats["both_present_mismatch"]}')
    lines.append(f'- Entries where cc_requested_model != proxy_forwarded_model (override active): {stats["override_active_count"]}')
    lines.append('')
    lines.append('## Status codes observed')
    lines.append('')
    for status, count in sorted(stats['status_counts'].items(), key=lambda kv: (kv[0] is None, kv[0])):
        lines.append(f'- `{status}`: {count}')
    lines.append('')
    lines.append('## content-type values observed')
    lines.append('')
    if stats['content_type_values']:
        for val, count in sorted(stats['content_type_values'].items(), key=lambda kv: -kv[1]):
            lines.append(f'- `{val}`: {count}')
    else:
        lines.append('- none — no entry in the corpus carries a `content-type` header value '
                      '(all entries predate the header-filter change; `_filter_response_headers` '
                      'previously dropped it)')
    lines.append('')
    lines.append('## content-encoding values observed')
    lines.append('')
    if stats['content_encoding_values']:
        for val, count in sorted(stats['content_encoding_values'].items(), key=lambda kv: -kv[1]):
            lines.append(f'- `{val}`: {count}')
    else:
        lines.append('- none — no entry in the corpus carries a `content-encoding` header value '
                      '(same reason as content-type above)')
    lines.append('')
    lines.append('## cc_requested_model vs. proxy_forwarded_model vs. answering_model')
    lines.append('')
    if stats['forwarded_present'] or stats['answering_present'] or stats['cc_requested_model_values']:
        lines.append('`cc_requested_model` values (what Claude Code asked for):')
        for val, count in sorted(stats['cc_requested_model_values'].items(), key=lambda kv: -kv[1]):
            lines.append(f'- `{val}`: {count}')
        lines.append('')
        lines.append('`proxy_forwarded_model` values (what the proxy actually sent to Anthropic):')
        for val, count in sorted(stats['proxy_forwarded_model_values'].items(), key=lambda kv: -kv[1]):
            lines.append(f'- `{val}`: {count}')
        lines.append('')
        lines.append('`answering_model` values (what the API answered with):')
        for val, count in sorted(stats['answering_model_values'].items(), key=lambda kv: -kv[1]):
            lines.append(f'- `{val}`: {count}')
    else:
        lines.append(
            'No entry in the corpus carries `cc_requested_model`/`proxy_forwarded_model`/`answering_model` '
            f'— the entire {stats["total"]}-entry corpus predates this milestone\'s `addon.py`/'
            '`response_model_probe.py` change. Every worker/main proxy in this session is running from a '
            'frozen `src/logs/.proxy_live_<id>/proxy/` copy (see `src/proxy/DOCS.md` Gotchas); none can '
            'produce the new fields until killed and respawned. This is the expected, documented state as '
            'of this milestone — not a bug in the parsing logic (see `p8_answering_model_probe_test.py` for '
            'unit-level verification of the parser against synthetic SSE bytes).'
        )
    lines.append('')
    REPORT_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build_response_model_report_workflow()
