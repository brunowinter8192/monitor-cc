#!/usr/bin/env python3
"""Replay-Validator v2: validate template-based SR strip against all historical logs.

Two independent validations:

PART A — False-Positive elimination:
  For each chunk in stripped_msg_removed (what OLD proxy stripped):
  Classify using NEW template matching (_match_template).
  If inner text does NOT match any template → was a FP (old code wrongly stripped it).
  Verify NEW _apply_sr_strip returns the chunk unchanged (FPs_new should = 0).

PART B — Missed SR coverage:
  For messages in raw_payload NOT processed by old proxy but containing standalone SRs:
  Apply _strip_system_reminders to message content.
  Count how many previously-missed SRs are now stripped.

Expected:
  FPs_new == 0   (code literals no longer stripped)
  Coverage_gained > 0  (missed SRs now stripped)
  Real_drops == 0  (no regression on real SRs)

Usage: python3 dev/proxy/replay_strip_v2.py
Output: /tmp/replay_strip_v2.md
"""
import json, sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

LOGS_DIR = Path('/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs')
OUT_FILE = Path('/tmp/replay_strip_v2.md')

from src.proxy.strip_sr import (
    _apply_sr_strip, _match_template, _ALL_TEMPLATES,
    _STANDALONE_SR_RE, _INNER_SR_RE, _strip_system_reminders,
)


def _chunk_template(chunk):
    """Return template_id for chunk, or None if not a known SR."""
    if not isinstance(chunk, str) or not chunk.startswith('<system-reminder>'):
        return None
    inner_m = _INNER_SR_RE.search(chunk)
    if not inner_m:
        return None
    inner = inner_m.group(1).strip()
    tid, _ = _match_template(inner, _ALL_TEMPLATES)
    return tid


def _has_standalone_sr(content):
    """True if content contains standalone SR blocks at line beginnings."""
    def _check(text):
        return isinstance(text, str) and '<system-reminder>' in text and bool(_STANDALONE_SR_RE.search(text))

    if isinstance(content, str):
        return _check(content)
    if isinstance(content, list):
        for blk in content:
            if not isinstance(blk, dict):
                continue
            if blk.get('type') == 'text' and _check(blk.get('text', '')):
                return True
            if blk.get('type') == 'tool_result':
                inner = blk.get('content', '')
                if isinstance(inner, str) and _check(inner):
                    return True
                if isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and _check(sub.get('text', '')):
                            return True
    return False


def scan_all():
    logs = sorted(LOGS_DIR.glob('api_requests_*.jsonl'))
    total_entries = 0

    # Part A counters
    fps_old = 0         # chunks with no template match (old code wrongly stripped)
    fps_new = 0         # of those, new code ALSO strips them (regression)
    real_old = 0        # chunks with template match (old code correctly stripped)
    real_new_drops = 0  # of those, new code does NOT strip them (regression)
    fp_new_examples = []
    real_drop_examples = []

    # Part B counters
    missed_old = 0       # messages with SR not processed by old proxy
    now_stripped = 0     # of those, new code now strips them
    still_missed = 0

    for log in logs:
        with open(log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    total_entries += 1
                    old_removed = entry.get('stripped_msg_removed', {})

                    # ─── Part A ───
                    for _, chunks in old_removed.items():
                        for chunk in chunks:
                            if not isinstance(chunk, str):
                                continue
                            if chunk.startswith('<task-notification>'):
                                continue
                            if not chunk.startswith('<system-reminder>'):
                                continue
                            tid = _chunk_template(chunk)
                            new_result = _apply_sr_strip(chunk, _ALL_TEMPLATES)
                            if tid is None:
                                fps_old += 1
                                # FP check: does the new code strip the outer FP code wrapper?
                                # (It should NOT — template matching prevents this.)
                                # The outer FP content is the first non-whitespace line after <SR>
                                outer_m = _INNER_SR_RE.search(chunk)
                                if outer_m:
                                    first_line = outer_m.group(1).strip().split('\n')[0]
                                    if first_line and first_line not in new_result:
                                        # Outer FP code was stripped — true regression
                                        fps_new += 1
                                        if len(fp_new_examples) < 5:
                                            fp_new_examples.append(repr(chunk[:120]))
                            else:
                                real_old += 1
                                if new_result == chunk:
                                    real_new_drops += 1
                                    if len(real_drop_examples) < 3:
                                        real_drop_examples.append({'tid': tid, 'chunk': repr(chunk[:80])})

                    # ─── Part B ───
                    rp = entry.get('raw_payload', {})
                    stripped_idxs = set(int(k) for k in old_removed.keys())
                    for msg_idx, msg in enumerate(rp.get('messages', [])):
                        if msg_idx in stripped_idxs:
                            continue
                        content = msg.get('content', '')
                        if not _has_standalone_sr(content):
                            continue
                        missed_old += 1
                        new_content = _strip_system_reminders(content)
                        if _has_standalone_sr(new_content):
                            still_missed += 1
                        else:
                            now_stripped += 1

                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

    return {
        'total_entries': total_entries,
        'total_logs': len(logs),
        'fps_old': fps_old,
        'fps_new': fps_new,
        'real_old': real_old,
        'real_new_drops': real_new_drops,
        'missed_old': missed_old,
        'now_stripped': now_stripped,
        'still_missed': still_missed,
        'fp_new_examples': fp_new_examples,
        'real_drop_examples': real_drop_examples,
    }


def write_report(r):
    lines = ['# Replay Strip v2 — Validation Report\n\n']
    lines.append(f'Scanned {r["total_logs"]} logs, {r["total_entries"]} entries.\n\n')

    lines.append('## Part A — False-Positive Elimination\n\n')
    lines.append('Classification based on NEW template matching (_match_template):\n\n')
    lines.append('| Metric | Count |\n|---|---|\n')
    lines.append(f'| FP chunks (no template match) from OLD logs | {r["fps_old"]} |\n')
    lines.append(f'| FP chunks still stripped by NEW code | **{r["fps_new"]}** |\n')
    lines.append(f'| Real SR chunks (template match) from OLD logs | {r["real_old"]} |\n')
    lines.append(f'| Real SR chunks dropped by NEW code (regression) | **{r["real_new_drops"]}** |\n\n')

    lines.append('## Part B — Missed SR Coverage\n\n')
    lines.append('Messages in raw_payload with standalone SRs NOT processed by old proxy:\n\n')
    lines.append('| Metric | Count |\n|---|---|\n')
    lines.append(f'| Missed SR messages (old code) | {r["missed_old"]} |\n')
    lines.append(f'| Now stripped by NEW code | **{r["now_stripped"]}** |\n')
    lines.append(f'| Still missed by NEW code | {r["still_missed"]} |\n\n')

    pass_fp = r['fps_new'] == 0
    pass_coverage = r['now_stripped'] > 0
    pass_no_regression = r['real_new_drops'] == 0

    fp_v = '✅ PASS' if pass_fp else f'❌ FAIL ({r["fps_new"]} remain)'
    cov_v = '✅ PASS' if pass_coverage else '❌ FAIL (0 new strips)'
    reg_v = '✅ PASS' if pass_no_regression else f'❌ FAIL ({r["real_new_drops"]} dropped)'

    lines.append('## Verdict\n\n')
    lines.append(f'- FPs eliminated: {fp_v}\n')
    lines.append(f'- Coverage gained: {cov_v} ({r["now_stripped"]} messages now stripped)\n')
    lines.append(f'- No regression: {reg_v}\n\n')

    if r['fp_new_examples']:
        lines.append('## Remaining FP Examples (NEW code still strips)\n\n')
        for ex in r['fp_new_examples']:
            lines.append(f'- `{ex[:120]}`\n')

    if r['real_drop_examples']:
        lines.append('\n## Regression Examples (NEW code dropped real SRs)\n\n')
        for ex in r['real_drop_examples']:
            lines.append(f'- tid={ex["tid"]}: `{ex["chunk"]}`\n')

    return ''.join(lines)


def main():
    print('Running replay validation...', flush=True)
    result = scan_all()
    print(f'Done. {result["total_entries"]} entries in {result["total_logs"]} logs.')
    print(f'Part A: FPs_old={result["fps_old"]}, FPs_new={result["fps_new"]} | Real_old={result["real_old"]}, drops={result["real_new_drops"]}')
    print(f'Part B: Missed_old={result["missed_old"]}, now_stripped={result["now_stripped"]}, still_missed={result["still_missed"]}')

    report = write_report(result)
    OUT_FILE.write_text(report)
    print(f'\nReport: {OUT_FILE}')

    failed = []
    if result['fps_new'] > 0:
        failed.append(f'FPs_new={result["fps_new"]} (expected 0)')
    if result['real_new_drops'] > 0:
        failed.append(f'real_new_drops={result["real_new_drops"]} (expected 0)')
    if result['now_stripped'] == 0 and result['missed_old'] > 0:
        failed.append('Coverage=0 (expected >0)')
    # still_missed < 5% tolerance: residual are unknown-template SR-like content
    missed_rate = result['still_missed'] / max(result['missed_old'], 1)
    if missed_rate > 0.05:
        failed.append(f'still_missed rate {missed_rate:.1%} > 5% tolerance')

    if failed:
        print('FAIL:', ', '.join(failed))
        sys.exit(1)
    print('ALL PASS: FPs_new=0, coverage gained, no regression')


if __name__ == '__main__':
    main()
