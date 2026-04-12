#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import re
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path

import tiktoken

REPORTS_DIR = Path(__file__).parent / "04_reports"
ENC = tiktoken.get_encoding("cl100k_base")
CONTEXT_CHARS = 500
KPI_THRESHOLD = 0.10

# ORCHESTRATOR

def main():
    args = parse_args()
    proxy_path = Path(args.proxy_log)
    session_path = Path(args.session_jsonl).expanduser()
    prev_proxy_path = Path(args.prev_proxy_log).expanduser() if args.prev_proxy_log else None
    req_n = args.req

    target_entry = load_proxy_entry(proxy_path, req_n)
    cr, cc, d, out = load_session_ground_truth(session_path, req_n)
    sys_rows, tools_rows, msg_rows, estimate = tokenize_segments(target_entry)

    attribution = None
    if prev_proxy_path and cr > 0:
        attribution = compute_prefix_attribution(target_entry, prev_proxy_path, cr, cc)

    rule_edits = compute_rule_edits(proxy_path, prev_proxy_path, attribution)
    report = build_report(
        req_n, proxy_path, session_path, cr, cc, d, out,
        sys_rows, tools_rows, msg_rows, estimate, attribution, rule_edits,
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"{ts}_req{req_n}.md"
    report_path.write_text(report)
    print(f"Report: {report_path}")

# FUNCTIONS

# Parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Forensic breakdown of proxy API request token attribution')
    parser.add_argument('--proxy-log', required=True, help='Proxy JSONL log file')
    parser.add_argument('--session-jsonl', required=True, help='Session JSONL file')
    parser.add_argument('--req', type=int, default=1, help='Request number 1-based, opus only (default: 1)')
    parser.add_argument('--prev-proxy-log', help='Previous session proxy log for prefix byte-diff attribution')
    return parser.parse_args()

# Load the N-th opus raw_payload entry (non-haiku, non-sent_meta) from proxy log in file order
def load_proxy_entry(proxy_path, req_n):
    opus_count = 0
    with open(proxy_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'raw_payload' not in entry:
                continue  # skip sent_meta entries
            if 'haiku' in entry.get('model', '').lower():
                continue
            opus_count += 1
            if opus_count == req_n:
                return entry
    raise ValueError(f"REQ#{req_n} not found — only {opus_count} opus raw_payload entries in proxy log")

# Load ground truth (CR, CC, D, Out) for the N-th opus API call in file order
# Dedup: consecutive type=assistant events with identical (CR, CC, D) = one streaming call → keep highest Out
def load_session_ground_truth(session_path, req_n):
    events = []
    pending_key = None
    pending_out = 0
    with open(session_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') != 'assistant':
                # Non-assistant events break streaming group (user turn between calls)
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                    pending_key = None
                    pending_out = 0
                continue
            msg = d.get('message', {})
            usage = msg.get('usage', {})
            if not usage:
                continue
            cr = usage.get('cache_read_input_tokens', 0) or 0
            cc_ = usage.get('cache_creation_input_tokens', 0) or 0
            inp = usage.get('input_tokens', 0) or 0
            out = usage.get('output_tokens', 0) or 0
            key = (cr, cc_, inp)
            if key == pending_key:
                if out > pending_out:
                    pending_out = out
            else:
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                pending_key = key
                pending_out = out
    if pending_key is not None:
        events.append((*pending_key, pending_out))

    if req_n > len(events):
        raise ValueError(f"REQ#{req_n} not found — only {len(events)} deduplicated events in session JSONL")
    cr, cc_, d, out = events[req_n - 1]
    return cr, cc_, d, out

# Tokenize all segments (system blocks, tools, messages) using tiktoken cl100k_base
def tokenize_segments(entry):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    sys_rows = []
    for i, block in enumerate(system):
        json_str = json.dumps(block, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        preview = block.get('text', '')[:60].replace('\n', ' ')
        sys_rows.append({
            'idx': i,
            'text_chars': len(block.get('text', '')),
            'json_chars': len(json_str),
            'tokens': toks,
            'cache_control': block.get('cache_control'),
            'preview': preview,
        })

    tools_rows = []
    for i, tool in enumerate(tools):
        json_str = json.dumps(tool, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        tools_rows.append({
            'idx': i,
            'name': tool.get('name', f'tool_{i}'),
            'json_chars': len(json_str),
            'tokens': toks,
        })

    msg_rows = []
    for i, msg in enumerate(messages):
        json_str = json.dumps(msg, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        content = msg.get('content', [])
        cc_blocks = []
        if isinstance(content, list):
            for j, blk in enumerate(content):
                if blk.get('cache_control'):
                    cc_blocks.append(j)
        preview = ''
        if isinstance(content, list) and content:
            preview = str(content[0].get('text', ''))[:40].replace('\n', ' ')
        elif isinstance(content, str):
            preview = content[:40].replace('\n', ' ')
        msg_rows.append({
            'idx': i,
            'role': msg.get('role', '?'),
            'json_chars': len(json_str),
            'tokens': toks,
            'cc_blocks': cc_blocks,
            'preview': preview,
        })

    estimate = (
        sum(r['tokens'] for r in sys_rows)
        + sum(r['tokens'] for r in tools_rows)
        + sum(r['tokens'] for r in msg_rows)
    )
    return sys_rows, tools_rows, msg_rows, estimate

# Compute byte-level prefix diff between current and previous session's last opus request
def compute_prefix_attribution(current_entry, prev_proxy_path, actual_cr, actual_cc):
    prev_entry = load_last_opus_entry(prev_proxy_path)
    if prev_entry is None:
        return {'error': 'No opus entry with raw_payload found in prev proxy log'}

    old_prefix = serialize_prefix(prev_entry)
    new_prefix = serialize_prefix(current_entry)

    # Byte-level comparison
    old_bytes = old_prefix.encode('utf-8')
    new_bytes = new_prefix.encode('utf-8')
    min_len = min(len(old_bytes), len(new_bytes))
    drift_byte = min_len  # default: one is prefix of the other
    for i in range(min_len):
        if old_bytes[i] != new_bytes[i]:
            drift_byte = i
            break

    # Convert byte offset to character offset in new_prefix string
    drift_char = len(new_bytes[:drift_byte].decode('utf-8', errors='replace'))

    # Tokenize before drift and from drift to last BP end (all char-based)
    tokens_before_drift = len(ENC.encode(new_prefix[:drift_char]))
    last_bp_end_char = compute_last_bp_end_char(current_entry, new_prefix)
    tokens_after_drift_to_last_bp = len(ENC.encode(new_prefix[drift_char:last_bp_end_char]))

    # Context ±CONTEXT_CHARS characters around drift
    ctx_start = max(0, drift_char - CONTEXT_CHARS)
    ctx_end = min(len(new_prefix), drift_char + CONTEXT_CHARS)
    old_drift_char = len(old_bytes[:drift_byte].decode('utf-8', errors='replace'))
    old_ctx_start = max(0, old_drift_char - CONTEXT_CHARS)
    old_ctx_end = min(len(old_prefix), old_drift_char + CONTEXT_CHARS)

    context = {
        'old': old_prefix[old_ctx_start:old_ctx_end],
        'new': new_prefix[ctx_start:ctx_end],
        'old_bytes_at_drift': repr(old_bytes[drift_byte:drift_byte + 20]) if drift_byte < len(old_bytes) else '(end of old)',
        'new_bytes_at_drift': repr(new_bytes[drift_byte:drift_byte + 20]) if drift_byte < len(new_bytes) else '(end of new)',
    }

    # Identify segment (system/tools/messages) the drift falls in
    segment = identify_segment_by_char(drift_char, current_entry)

    # Find nearest markdown heading if drift is in sys[2]
    nearest_heading = None
    if segment.get('block_type') == 'system' and segment.get('block_idx') == 2:
        nearest_heading = find_nearest_heading(new_prefix, drift_char)

    # KPI
    cr_delta = abs(tokens_before_drift - actual_cr) / actual_cr if actual_cr > 0 else None
    cc_delta = abs(tokens_after_drift_to_last_bp - actual_cc) / actual_cc if actual_cc > 0 else None

    return {
        'drift_byte': drift_byte,
        'drift_char': drift_char,
        'common_prefix_bytes': drift_byte,
        'total_new_bytes': len(new_bytes),
        'total_old_bytes': len(old_bytes),
        'tokens_before_drift': tokens_before_drift,
        'tokens_after_drift_to_last_bp': tokens_after_drift_to_last_bp,
        'last_bp_end_char': last_bp_end_char,
        'segment': segment,
        'context': context,
        'nearest_heading': nearest_heading,
        'cr_kpi_pct': cr_delta,
        'cc_kpi_pct': cc_delta,
        'cr_kpi_pass': cr_delta is not None and cr_delta < KPI_THRESHOLD,
        'cc_kpi_pass': cc_delta is not None and cc_delta < KPI_THRESHOLD,
    }

# Stream-scan prev proxy log line by line (never loads full file), return last opus entry
def load_last_opus_entry(prev_proxy_path):
    last_entry = None
    with open(prev_proxy_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = entry.get('model', '').lower()
            if 'haiku' in model:
                continue
            if 'raw_payload' in entry:
                last_entry = entry
    return last_entry

# Serialize request prefix identically for both old and new entries
# Approximates Anthropic's internal cache key — KPI D5 measures accuracy
def serialize_prefix(entry):
    rp = entry.get('raw_payload', {})
    parts = [
        json.dumps(rp.get('system', []), ensure_ascii=False),
        json.dumps(rp.get('tools', []), ensure_ascii=False),
        json.dumps(rp.get('messages', []), ensure_ascii=False),
    ]
    return "\n".join(parts)

# Compute character offset of end of last BP message in serialized prefix string
def compute_last_bp_end_char(entry, full_prefix):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    last_bp_idx = find_last_bp_message_index(messages)

    system_json = json.dumps(system, ensure_ascii=False)
    tools_json = json.dumps(tools, ensure_ascii=False)
    msgs_offset_char = len(system_json) + 1 + len(tools_json) + 1  # +1 for each \n separator

    if last_bp_idx < 0:
        return len(full_prefix)  # No BP in messages → use full prefix length

    # partial_msgs_json = json.dumps(messages[:M+1]) = "[m0, ..., mM]"
    # Removing the closing ] gives "[m0, ..., mM" which is a prefix of json.dumps(messages)
    partial_msgs_json = json.dumps(messages[:last_bp_idx + 1], ensure_ascii=False)
    last_bp_end_in_msgs = len(partial_msgs_json) - 1  # char position after last BP msg content
    return msgs_offset_char + last_bp_end_in_msgs

# Find index of last message containing a cache_control block
def find_last_bp_message_index(messages):
    last_idx = -1
    for i, msg in enumerate(messages):
        content = msg.get('content', [])
        if isinstance(content, list):
            for block in content:
                if block.get('cache_control'):
                    last_idx = i
                    break
        elif isinstance(content, dict) and content.get('cache_control'):
            last_idx = i
    return last_idx

# Identify which segment and block the drift char position falls in
def identify_segment_by_char(drift_char, entry):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    system_json = json.dumps(system, ensure_ascii=False)
    tools_json = json.dumps(tools, ensure_ascii=False)

    sys_end = len(system_json)
    tools_start = sys_end + 1
    tools_end = tools_start + len(tools_json)
    msgs_start = tools_end + 1

    if drift_char <= sys_end:
        offset_in_section = drift_char
        cumulative = 1  # opening `[`
        for i, block in enumerate(system):
            block_json = json.dumps(block, ensure_ascii=False)
            block_end = cumulative + len(block_json)
            if offset_in_section <= block_end:
                return {'block_type': 'system', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = block_end + 2  # `, ` separator
        return {'block_type': 'system', 'block_idx': len(system) - 1, 'char_offset': offset_in_section}

    elif drift_char <= tools_end:
        offset_in_section = drift_char - tools_start
        cumulative = 1
        for i, tool in enumerate(tools):
            tool_json = json.dumps(tool, ensure_ascii=False)
            tool_end = cumulative + len(tool_json)
            if offset_in_section <= tool_end:
                return {'block_type': 'tools', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = tool_end + 2
        return {'block_type': 'tools', 'block_idx': len(tools) - 1, 'char_offset': offset_in_section}

    else:
        offset_in_section = drift_char - msgs_start
        cumulative = 1
        for i, msg in enumerate(messages):
            msg_json = json.dumps(msg, ensure_ascii=False)
            msg_end = cumulative + len(msg_json)
            if offset_in_section <= msg_end:
                return {'block_type': 'messages', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = msg_end + 2
        return {'block_type': 'messages', 'block_idx': len(messages) - 1, 'char_offset': offset_in_section}

# Find nearest markdown heading at or before drift_char in the serialized prefix
def find_nearest_heading(prefix_text, drift_char):
    text_before = prefix_text[:drift_char]
    matches = list(re.finditer(r'^#{1,3} .+', text_before, re.MULTILINE))
    if matches:
        return matches[-1].group(0)[:120]
    return None

# Compute rule edit correlation — check git log + file mtimes in time window between sessions
def compute_rule_edits(proxy_path, prev_proxy_path, attribution):
    curr_ts = _extract_timestamp_from_path(proxy_path)
    prev_ts = _extract_timestamp_from_path(prev_proxy_path) if prev_proxy_path else None

    result = {
        'curr_ts': curr_ts,
        'prev_ts': prev_ts,
        'git_log': None,
        'mtime_files': [],
        'drift_match': None,
    }

    shared_rules = Path.home() / '.claude' / 'shared-rules'
    is_git_repo = False
    if shared_rules.exists():
        try:
            subprocess.run(
                ['git', '-C', str(shared_rules), 'status'],
                capture_output=True, check=True,
            )
            is_git_repo = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if is_git_repo and prev_ts and curr_ts:
        prev_dt = datetime.fromtimestamp(prev_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        curr_dt = datetime.fromtimestamp(curr_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        try:
            proc = subprocess.run(
                ['git', '-C', str(shared_rules), 'log',
                 f'--since={prev_dt}', f'--until={curr_dt}',
                 '--name-only', '--pretty=format:%h %cI %s'],
                capture_output=True, text=True,
            )
            result['git_log'] = proc.stdout.strip() or '(no commits in window)'
        except Exception as e:
            result['git_log'] = f'Error: {e}'

    # Check file mtimes for rule directories
    rule_dirs = [
        Path.home() / '.claude' / 'shared-rules' / 'global',
        Path.home() / '.claude' / 'rules',
    ]
    for rule_dir in rule_dirs:
        if not rule_dir.exists():
            continue
        for md_file in sorted(rule_dir.glob('*.md')):
            mtime = md_file.stat().st_mtime
            if prev_ts and curr_ts and prev_ts <= mtime <= curr_ts:
                result['mtime_files'].append({
                    'path': str(md_file),
                    'mtime': mtime,
                    'mtime_str': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'drift_match': None,
                })

    # Cross-check drift context text against content of modified files
    if attribution and not attribution.get('error') and result['mtime_files']:
        drift_context = attribution.get('context', {}).get('new', '')
        for f_info in result['mtime_files']:
            try:
                file_content = Path(f_info['path']).read_text()
                overlap = _find_text_overlap(drift_context, file_content)
                if overlap:
                    f_info['drift_match'] = overlap
                    if result['drift_match'] is None:
                        result['drift_match'] = f_info['path']
            except Exception:
                pass

    return result

# Extract Unix timestamp integer from proxy log filename
def _extract_timestamp_from_path(path):
    if path is None:
        return None
    name = Path(path).stem
    for part in reversed(name.split('_')):
        if part.isdigit() and len(part) >= 9:
            return int(part)
    return None

# Find a significant text overlap between context snippet and file content
def _find_text_overlap(context_text, file_content):
    chunk_size = 80
    step = 20
    for i in range(0, max(0, len(context_text) - chunk_size), step):
        chunk = context_text[i:i + chunk_size].strip()
        if len(chunk) < 40:
            continue
        if chunk in file_content:
            return chunk
    return None

# Build the full markdown report
def build_report(req_n, proxy_path, session_path, cr, cc, d, out,
                  sys_rows, tools_rows, msg_rows, estimate, attribution, rule_edits):
    total_actual = cr + cc + d
    delta = estimate - total_actual
    delta_pct = abs(delta) / total_actual * 100 if total_actual > 0 else 0
    kpi_d2 = '✅ PASS' if delta_pct < KPI_THRESHOLD * 100 else '❌ FAIL'

    lines = [
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

    lines.extend([
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
    ])

    if attribution:
        if attribution.get('error'):
            lines.extend([
                '## Prefix Attribution',
                '',
                f'**Error:** {attribution["error"]}',
                '',
            ])
        else:
            cr_est = attribution['tokens_before_drift']
            cc_est = attribution['tokens_after_drift_to_last_bp']
            cr_kpi = '✅ PASS' if attribution.get('cr_kpi_pass') else '❌ FAIL'
            cc_kpi = '✅ PASS' if attribution.get('cc_kpi_pass') else '❌ FAIL'
            cr_pct = (attribution.get('cr_kpi_pct') or 0) * 100
            cc_pct = (attribution.get('cc_kpi_pct') or 0) * 100

            seg = attribution['segment']
            seg_str = f"{seg['block_type']}[{seg['block_idx']}] char_offset {seg['char_offset']:,}"

            lines.extend([
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
            ])
            if attribution.get('nearest_heading'):
                lines.append(f'- **Nearest heading:** `{attribution["nearest_heading"]}`')

            ctx = attribution['context']
            lines.extend([
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
            ])

    if rule_edits:
        lines.extend([
            '## Rule Edit Correlation',
            '',
        ])
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

    lines.extend([
        '## Conclusion',
        '',
    ])
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

    return '\n'.join(lines)


if __name__ == '__main__':
    main()
