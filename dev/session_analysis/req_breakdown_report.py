# INFRASTRUCTURE
import json
from datetime import datetime

from req_breakdown_attribution import KPI_THRESHOLD

# FUNCTIONS

def _build_header_and_ground_truth_lines(req_n, proxy_path, session_path, cr, cc, d, out, total_actual):
    return [
        f'# REQ#{req_n} Breakdown Report',
        '',
        f'**Proxy log:** `{proxy_path}`',
        f'**Session JSONL:** `{session_path}`',
        f'**Timestamp:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '## Ground Truth (from session JSONL)',
        '',
        f'| Field | Value |',
        f'|---|---|',
        f'| CR (cache_read) | {cr:,} |',
        f'| CC (cache_creation) | {cc:,} |',
        f'| D (direct input) | {d:,} |',
        f'| Out | {out:,} |',
        f'| Total input (CR+CC+D) | {total_actual:,} |',
        '',
    ]

def _build_segment_tables_lines(sys_rows, tools_rows, msg_rows):
    lines = [
        '## Segment Breakdown (tiktoken cl100k_base)',
        '',
        '### System blocks',
        '',
        '| idx | text_chars | tokens | cache_control | preview |',
        '|---|---|---|---|---|',
    ]
    for r in sys_rows:
        cc_str = json.dumps(r['cache_control']) if r['cache_control'] else '-'
        lines.append(f"| {r['idx']} | {r['text_chars']:,} | {r['tokens']:,} | {cc_str} | `{r['preview'][:50]}` |")
    sys_total_tokens = sum(r['tokens'] for r in sys_rows)
    lines.append(f'| **total** | | **{sys_total_tokens:,}** | | |')

    lines.extend([
        '',
        f'### Tools ({len(tools_rows)})',
        '',
        '| idx | name | json_chars | tokens |',
        '|---|---|---|---|',
    ])
    for r in tools_rows:
        lines.append(f"| {r['idx']} | {r['name']} | {r['json_chars']:,} | {r['tokens']:,} |")
    tools_total = sum(r['tokens'] for r in tools_rows)
    lines.append(f'| **total** | | | **{tools_total:,}** |')

    lines.extend([
        '',
        f'### Messages ({len(msg_rows)})',
        '',
        '| idx | role | json_chars | tokens | cc_blocks | preview |',
        '|---|---|---|---|---|---|',
    ])
    for r in msg_rows:
        cc_str = str(r['cc_blocks']) if r['cc_blocks'] else '-'
        lines.append(f"| {r['idx']} | {r['role']} | {r['json_chars']:,} | {r['tokens']:,} | {cc_str} | `{r['preview'][:40]}` |")
    msg_total = sum(r['tokens'] for r in msg_rows)
    lines.append(f'| **total** | | | **{msg_total:,}** | | |')
    return lines

def _build_totals_lines(estimate, total_actual, delta, delta_pct, kpi_d2):
    return [
        '',
        '## Totals',
        '',
        f'| Metric | Value |',
        f'|---|---|',
        f'| Estimate (tiktoken sum) | {estimate:,} |',
        f'| Actual (CR+CC+D) | {total_actual:,} |',
        f'| Delta | {delta:+,} ({delta_pct:.1f}%) |',
        f'| **KPI D2 (delta < 10%)** | **{kpi_d2}** |',
        '',
    ]

def _build_attribution_table_lines(attribution, cr, cc):
    cr_est = attribution['tokens_before_drift']
    cc_est = attribution['tokens_after_drift_to_last_bp']
    cr_kpi = '✅ PASS' if attribution.get('cr_kpi_pass') else '❌ FAIL'
    cc_kpi = '✅ PASS' if attribution.get('cc_kpi_pass') else '❌ FAIL'
    cr_pct = (attribution.get('cr_kpi_pct') or 0) * 100
    cc_pct = (attribution.get('cc_kpi_pct') or 0) * 100

    seg = attribution['segment']
    seg_str = f"{seg['block_type']}[{seg['block_idx']}] char_offset {seg['char_offset']:,}"

    lines = [
        '## Prefix Attribution (vs previous session)',
        '',
        f'| Metric | Value |',
        f'|---|---|',
        f'| Common prefix bytes | {attribution["common_prefix_bytes"]:,} |',
        f'| Drift byte position | {attribution["drift_byte"]:,} |',
        f'| Drift char position | {attribution["drift_char"]:,} |',
        f'| Total new prefix bytes | {attribution["total_new_bytes"]:,} |',
        f'| Total old prefix bytes | {attribution["total_old_bytes"]:,} |',
        f'| Tokens before drift (CR estimate) | {cr_est:,} |',
        f'| Tokens drift→last BP (CC estimate) | {cc_est:,} |',
        f'| **KPI D5 CR** actual={cr:,} vs est={cr_est:,} delta={cr_pct:.1f}% | **{cr_kpi}** |',
        f'| **KPI D5 CC** actual={cc:,} vs est={cc_est:,} delta={cc_pct:.1f}% | **{cc_kpi}** |',
        '',
        '## Drift Location',
        '',
        f'- **Segment:** {seg_str}',
    ]
    if attribution.get('nearest_heading'):
        lines.append(f'- **Nearest heading:** `{attribution["nearest_heading"]}`')
    return lines

def _build_attribution_context_lines(attribution, req_n):
    ctx = attribution['context']
    return [
        '',
        '## Drift Context (±500 chars)',
        '',
        '### OLD (prev session last opus request)',
        '```',
        ctx['old'],
        '```',
        '',
        '### NEW (current session REQ#' + str(req_n) + ')',
        '```',
        ctx['new'],
        '```',
        '',
        '### Byte-level diff',
        f'First differing byte at position **{attribution["drift_byte"]:,}**:',
        '',
        f'- OLD bytes: `{ctx["old_bytes_at_drift"]}`',
        f'- NEW bytes: `{ctx["new_bytes_at_drift"]}`',
        '',
    ]

def _build_attribution_lines(attribution, req_n, cr, cc):
    if not attribution:
        return []
    if attribution.get('error'):
        return [
            '## Prefix Attribution',
            '',
            f'**Error:** {attribution["error"]}',
            '',
        ]
    lines = _build_attribution_table_lines(attribution, cr, cc)
    lines.extend(_build_attribution_context_lines(attribution, req_n))
    return lines

def _build_rule_edits_lines(rule_edits):
    if not rule_edits:
        return []
    lines = [
        '## Rule Edit Correlation',
        '',
    ]
    if rule_edits.get('prev_ts') and rule_edits.get('curr_ts'):
        prev_dt = datetime.fromtimestamp(rule_edits['prev_ts']).strftime('%Y-%m-%d %H:%M:%S')
        curr_dt = datetime.fromtimestamp(rule_edits['curr_ts']).strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f'- **Time window:** {prev_dt} → {curr_dt} (local)')
    if rule_edits.get('git_log') is not None:
        lines.extend([
            f'- **Git log (shared-rules in window):**',
            '  ```',
            f'  {rule_edits["git_log"][:600]}',
            '  ```',
        ])
    mtime_files = rule_edits.get('mtime_files', [])
    if mtime_files:
        lines.append('- **Files modified in window:**')
        for fi in mtime_files:
            match = fi.get('drift_match')
            match_str = f'\n  → **DRIFT MATCH:** `{match[:100]}`' if match else ''
            lines.append(f'  - `{fi["path"]}` (mtime {fi["mtime_str"]}){match_str}')
    else:
        lines.append('- No rule files modified in time window')

    if rule_edits.get('drift_match'):
        lines.append(f'\n**→ HYPOTHESIS: CONFIRMED** — drift content matched in `{rule_edits["drift_match"]}`')
    elif mtime_files:
        lines.append('\n**→ HYPOTHESIS: UNVERIFIED** — files modified in window but drift context text not found in file (may be deleted content)')
    else:
        lines.append('\n**→ HYPOTHESIS: REJECTED** — no rule file edits found in time window')
    lines.append('')
    return lines

def _build_conclusion_lines(attribution, rule_edits, cr):
    lines = [
        '## Conclusion',
        '',
    ]
    if attribution and not attribution.get('error'):
        seg = attribution['segment']
        cr_pass = attribution.get('cr_kpi_pass')
        conclusion_parts = [
            f'Byte-level prefix diff places drift at **{seg["block_type"]}[{seg["block_idx"]}]** '
            f'(char offset {seg["char_offset"]:,}).',
        ]
        if attribution.get('nearest_heading'):
            conclusion_parts.append(f'Nearest heading: `{attribution["nearest_heading"]}`.')
        if cr_pass:
            conclusion_parts.append(
                f'CR KPI PASS: {attribution["tokens_before_drift"]:,} estimated vs {cr:,} actual '
                f'({(attribution.get("cr_kpi_pct") or 0)*100:.1f}% delta) — '
                'validates that tokens before drift = cache-read tokens.'
            )
        else:
            conclusion_parts.append(
                f'CR KPI FAIL: {attribution["tokens_before_drift"]:,} estimated vs {cr:,} actual '
                f'({(attribution.get("cr_kpi_pct") or 0)*100:.1f}% delta) — '
                "our prefix serialization does not precisely match Anthropic's internal cache key."
            )
        if rule_edits and rule_edits.get('drift_match'):
            conclusion_parts.append(
                f'Rule file edit confirmed as cause: drift content matched in `{rule_edits["drift_match"]}`.'
            )
        lines.append(' '.join(conclusion_parts))
    else:
        lines.append('_Prefix attribution not computed (requires --prev-proxy-log and CR > 0)._')
    return lines

def build_report(req_n, proxy_path, session_path, cr, cc, d, out,
                  sys_rows, tools_rows, msg_rows, estimate, attribution, rule_edits):
    total_actual = cr + cc + d
    delta = estimate - total_actual
    delta_pct = abs(delta) / total_actual * 100 if total_actual > 0 else 0
    kpi_d2 = '✅ PASS' if delta_pct < KPI_THRESHOLD * 100 else '❌ FAIL'

    lines = []
    lines.extend(_build_header_and_ground_truth_lines(req_n, proxy_path, session_path, cr, cc, d, out, total_actual))
    lines.extend(_build_segment_tables_lines(sys_rows, tools_rows, msg_rows))
    lines.extend(_build_totals_lines(estimate, total_actual, delta, delta_pct, kpi_d2))
    lines.extend(_build_attribution_lines(attribution, req_n, cr, cc))
    lines.extend(_build_rule_edits_lines(rule_edits))
    lines.extend(_build_conclusion_lines(attribution, rule_edits, cr))
    return '\n'.join(lines)
