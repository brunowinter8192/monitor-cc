# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path

from tag_presence_audit_scan import _SR_TEMPLATES

# FUNCTIONS

def _build_tag_and_sr_tables(tag_counts, sr_bypassed, sr_captured):
    lines = [
        '### Tag Type Counts',
        '',
        '| tag | occurrences_in_delta |',
        '|---|---|',
    ]
    for tag_type, label in (('SR', '`<SR>`'), ('TN', '`<TN>`'), ('ND', '`<ND>`'), ('PO', '`<PO>`')):
        lines.append(f'| {label} | {tag_counts[tag_type]} |')
    lines += [
        '',
        '### SR Template Breakdown',
        '',
        '| template_id | bypassed_in_delta | captured_in_delta | bypass_rate |',
        '|---|---|---|---|',
    ]
    for tid in _SR_TEMPLATES:
        b = sr_bypassed[tid]
        c = sr_captured[tid]
        total = b + c
        rate = 'n/a' if total == 0 else f'{100 * b / total:.1f}%'
        lines.append(f'| {tid} | {b} | {c} | {rate} |')
    return lines


def _build_non_sr_table(tn_bypassed, tn_captured, nd_bypassed, nd_captured, po_bypassed, po_captured):
    lines = [
        '',
        '### Non-SR Tag Strip Verification',
        '',
        '| tag_type | bypassed_in_delta | captured_in_delta | bypass_rate |',
        '|---|---|---|---|',
    ]
    for tag_label, byp, cap in (
        ('task-notification', tn_bypassed, tn_captured),
        ('new-diagnostics',   nd_bypassed, nd_captured),
        ('persisted-output (preview)', po_bypassed, po_captured),
    ):
        total = byp + cap
        rate = 'n/a' if total == 0 else f'{100 * byp / total:.1f}%'
        lines.append(f'| {tag_label} | {byp} | {cap} | {rate} |')
    return lines


def _build_aggregate(tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags,
                     tn_bypassed, tn_captured, nd_bypassed, nd_captured,
                     po_bypassed, po_captured):
    total_tags = sum(tag_counts.values())
    lines = ['## Aggregate (delta-scoped)', '']
    lines += _build_tag_and_sr_tables(tag_counts, sr_bypassed, sr_captured)
    lines += _build_non_sr_table(tn_bypassed, tn_captured, nd_bypassed, nd_captured,
                                 po_bypassed, po_captured)
    lines += [
        '',
        f'Total opus REQs: {n_opus} | REQs with tag occurrences in delta: {n_reqs_with_tags}'
        f' | Total tag occurrences: {total_tags}',
        '',
    ]
    return lines


def _build_report(jsonl_path, blocks, tag_counts, sr_bypassed, sr_captured,
                  n_opus, n_reqs_with_tags, n_non_opus,
                  tn_bypassed, tn_captured, nd_bypassed, nd_captured, po_bypassed, po_captured):
    total_tags = sum(tag_counts.values())
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# Tag Presence Audit — {ts}',
        '',
        f'Source: `{Path(jsonl_path).name}`',
        f'Opus entries: {n_opus}  |  Non-opus (skipped): {n_non_opus}',
        f'REQs with tag occurrences in delta: {n_reqs_with_tags}  |  Total tag occurrences: {total_tags}',
        '',
        '---',
        '',
    ]
    lines.extend(blocks)
    lines.extend(_build_aggregate(tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags,
                                  tn_bypassed, tn_captured, nd_bypassed, nd_captured,
                                  po_bypassed, po_captured))
    return lines
