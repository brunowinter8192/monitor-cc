#!/usr/bin/env python3
"""CC injection catalog via proxy-log / session-JSONL cross-reference.

For each user-role message in the delta range of each opus REQ, checks whether
the message content appears as a real user event in the matching CC session JSONL.
Unmatched messages are CC-injected; classified by startswith pattern.

Cross-reference key: first 80 chars of normalized text (str direct / text-block concat).
Minimum text length: 20 chars (filters empty tool_result wrappers and noise).

Auto-discovery: CC session JSONL is selected by mtime proximity to the proxy log
(max 90 min); override with --cc-session.

Input:  one or more proxy log paths (positional args); default: newest 5
        src/logs/api_requests_opus_monitor_cc_*.jsonl
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_cc_injection_catalog.md
"""

# INFRASTRUCTURE

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def _resolve_repo_root():
    if 'MONITOR_CC_ROOT' in os.environ:
        return Path(os.environ['MONITOR_CC_ROOT'])
    # Walk up from __file__; prefer the root that has src/logs/ (handles worktrees)
    candidate = Path(__file__).parent.parent.parent
    if (candidate / 'src' / 'logs').is_dir():
        return candidate
    # Worktree: git --git-common-dir points to main .git → parent is main repo root
    try:
        import subprocess
        git_common = subprocess.run(
            ['git', 'rev-parse', '--git-common-dir'],
            capture_output=True, text=True, cwd=str(candidate),
        ).stdout.strip()
        if git_common:
            main_root = Path(git_common).resolve().parent
            if (main_root / 'src' / 'logs').is_dir():
                return main_root
    except Exception:
        pass
    return candidate

_REPO_ROOT = _resolve_repo_root()
_CC_PROJECT_DIR = Path.home() / '.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC'
_MIN_TEXT_LEN = 20   # chars — below this, delta user-msgs are noise
_MTIME_CAP_SEC = 90 * 60  # 90 minutes max mtime diff for auto-discovery

# ORCHESTRATOR

def cc_injection_audit_workflow(proxy_log_paths, cc_session_override, output_path):
    all_hits = []
    session_cache = {}  # proxy_log → cc_session_path used

    for proxy_log in proxy_log_paths:
        if cc_session_override:
            cc_session = Path(cc_session_override)
        else:
            cc_session = _find_matching_cc_session(proxy_log, _CC_PROJECT_DIR)
        session_cache[proxy_log] = cc_session

        if cc_session is None:
            print(f'WARN: no CC session found within 90 min of {proxy_log.name} — skipping', file=sys.stderr)
            continue

        cc_heads = _build_cc_user_index(cc_session)
        hits = _scan_proxy_log(proxy_log, cc_heads)
        for h in hits:
            h['proxy_log'] = proxy_log.name
            h['cc_session'] = cc_session.name
        all_hits.extend(hits)

    report = _build_report(all_hits, proxy_log_paths, session_cache)
    output_path.write_text(report)
    print(output_path)

# FUNCTIONS

# Return CC session JSONL with smallest mtime diff to proxy log, or None if none within cap
def _find_matching_cc_session(proxy_log, cc_project_dir):
    if not cc_project_dir.is_dir():
        return None
    proxy_mtime = proxy_log.stat().st_mtime
    best, best_diff = None, float('inf')
    for f in cc_project_dir.glob('*.jsonl'):
        diff = abs(f.stat().st_mtime - proxy_mtime)
        if diff < best_diff:
            best, best_diff = f, diff
    if best_diff <= _MTIME_CAP_SEC:
        return best
    return None


# Build set of head-80 strings from all user events in CC session JSONL
def _build_cc_user_index(cc_session_path):
    heads = set()
    for line in cc_session_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get('type') != 'user':
            continue
        content = ev.get('message', {}).get('content', '')
        if isinstance(content, str):
            t = content.strip()
            if len(t) >= _MIN_TEXT_LEN:
                heads.add(t[:80])
        elif isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get('type') == 'text':
                    t = blk.get('text', '').strip()
                    if len(t) >= _MIN_TEXT_LEN:
                        heads.add(t[:80])
    return heads


# Normalize message content to a single text blob; returns '' for tool_result/tool_use
def _normalize_msg_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            blk.get('text', '')
            for blk in content
            if isinstance(blk, dict) and blk.get('type') == 'text'
        ]
        return '\n'.join(parts)
    return ''


# Classify an unmatched injection by content startswith pattern
def _classify_injection(normalized_text, payload):
    if normalized_text.startswith('The user stepped away and is coming back.'):
        return 'IDLE_RECAP'
    if normalized_text.startswith('[SIDECAR_STRIPPED_'):
        return 'SIDECAR_STRIPPED'
    msgs = payload.get('messages', [])
    system = payload.get('system', '')
    sys_text = system if isinstance(system, str) else ''.join(
        b.get('text', '') if isinstance(b, dict) else ''
        for b in (system if isinstance(system, list) else [])
    )
    if len(msgs) == 1 and len(sys_text.strip()) <= 10:
        return 'SIDECAR'
    slug = hashlib.sha1(normalized_text[:80].encode()).hexdigest()[:8]
    return f'UNKNOWN_{slug}'


# Scan one proxy log; return list of hit dicts for each unmatched delta user-msg
def _scan_proxy_log(proxy_log, cc_heads):
    hits = []
    lines = [l for l in proxy_log.read_text().splitlines() if l.strip()]
    req_num = 0
    for line_idx, raw in enumerate(lines):
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        model = entry.get('model', '')
        if not model.startswith('claude-opus-'):
            continue
        req_num += 1
        diff = entry.get('diff_from_prev') or {}
        start = diff.get('first_diff_index', 0) if diff else 0
        rp = entry.get('raw_payload') or {}
        msgs = rp.get('messages') or []
        for msg_idx, msg in enumerate(msgs):
            if msg_idx < start:
                continue
            if msg.get('role') != 'user':
                continue
            normalized = _normalize_msg_content(msg.get('content', '')).strip()
            if len(normalized) < _MIN_TEXT_LEN:
                continue
            head = normalized[:80]
            if head in cc_heads:
                continue
            classification = _classify_injection(normalized, rp)
            hits.append({
                'req_num': req_num,
                'line_idx': line_idx,
                'msg_idx': msg_idx,
                'classification': classification,
                'head': head,
                'length': len(normalized),
            })
    return hits


# Build the MD catalog report from all hits across all proxy logs
def _build_report(all_hits, proxy_log_paths, session_cache):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# CC Injection Catalog',
        f'',
        f'Generated: {ts}',
        f'',
        f'## Proxy Logs Scanned',
        f'',
    ]
    for p in proxy_log_paths:
        cc = session_cache.get(p)
        cc_name = cc.name if cc else '(no match)'
        lines.append(f'- `{p.name}` → CC session `{cc_name}`')
    lines.append('')

    if not all_hits:
        lines.append('*No CC injections detected.*')
        return '\n'.join(lines)

    # Group by classification
    by_class = defaultdict(list)
    for h in all_hits:
        by_class[h['classification']].append(h)

    lines += [
        f'## Summary',
        f'',
        f'| Classification | Count | Known Strip Rule |',
        f'|---|---|---|',
    ]
    rule_map = {
        'IDLE_RECAP':        '`stripped_idle_recap` (67q)',
        'SIDECAR':           '`stripped_sidecar_content` (0jk)',
        'SIDECAR_STRIPPED':  '`stripped_sidecar_content` (0jk, already applied)',
    }
    for cls in sorted(by_class):
        count = len(by_class[cls])
        rule = rule_map.get(cls, '*(unknown)*')
        lines.append(f'| `{cls}` | {count} | {rule} |')
    lines.append('')

    # Detail per classification
    for cls in sorted(by_class):
        hits = by_class[cls]
        lines += [
            f'## {cls}',
            f'',
            f'| proxy_log | req# | line_idx | msg_idx | len | head[80c] |',
            f'|---|---|---|---|---|---|',
        ]
        # Deduplicate by head for the table (show unique patterns first, then occurrences)
        seen_heads = {}
        for h in hits:
            head = h['head']
            if head not in seen_heads:
                seen_heads[head] = []
            seen_heads[head].append(h)

        for head, group in sorted(seen_heads.items(), key=lambda x: -len(x[1])):
            for h in group:
                head_cell = head.replace('|', '\\|').replace('\n', '↵')[:80]
                lines.append(
                    f"| `{h['proxy_log'][:30]}` | {h['req_num']} | {h['line_idx']} "
                    f"| {h['msg_idx']} | {h['length']} | `{head_cell}` |"
                )
        lines.append('')

    return '\n'.join(lines)


def _parse_args():
    parser = argparse.ArgumentParser(description='CC injection catalog via proxy/session-JSONL cross-reference')
    parser.add_argument(
        'proxy_logs', nargs='*',
        help='Proxy log paths (default: newest 5 src/logs/api_requests_opus_monitor_cc_*.jsonl)',
    )
    parser.add_argument('--cc-session', help='CC session JSONL path (overrides auto-discovery)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    src_logs = Path(_REPO_ROOT) / 'src/logs'
    if args.proxy_logs:
        proxy_log_paths = [Path(p) for p in args.proxy_logs]
    else:
        all_logs = sorted(
            src_logs.glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        proxy_log_paths = all_logs[:5]

    ts = datetime.now().strftime('%Y%m%d%H%M')
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f'dev/tool_use_analysis/{ts}_cc_injection_catalog.md')

    return proxy_log_paths, args.cc_session, output_path


if __name__ == '__main__':
    proxy_log_paths, cc_session_override, output_path = _parse_args()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cc_injection_audit_workflow(proxy_log_paths, cc_session_override, output_path)
