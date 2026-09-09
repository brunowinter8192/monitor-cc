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
import importlib
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

# Structural passes (own logic) stayed in message_passes.py; template passes (generic pass
# runner + declarative spec) moved to message_passes_simple.py; the wake-up concern moved to
# message_passes_wakeup.py (2026-09, helper-extraction milestone).
from proxy.message_passes import (
    _apply_role_system_strip,
    _apply_first_pass,
    _apply_cumulative_sr_strips,
    _apply_final_sr_pass,
)
from proxy.message_passes_simple import (
    _apply_sn_notice_strip,
    _apply_po_preview_strip,
    _apply_bg_exit_strip,
    _apply_bg_launch_ack_strip,
    _apply_hook_prefix_strip,
    _apply_git_lock_strip,
    _apply_bd_noise_strip,
)
from proxy.message_passes_wakeup import _dedup_wakeup_blocks
from proxy.rule_ops import _block_inner_text
from proxy.diff_engine import compose_block
from proxy.payload_helpers import _top_level_content_contains
from proxy.content_strip import _message_has_rejection

# proxy_display/pane.py (pulled in by proxy_display/__init__.py) uses a 2-level relative
# import ("from ..constants") that requires proxy_display to be resolved as a SUBPACKAGE of
# the project root, not as a flat top-level package like the src/proxy/* imports above —
# resolved via a second sys.path root + dynamic import (dodges static "from src." rewriting).
sys.path.insert(0, str(WORKTREE_ROOT))
_src_pkg = 'src'
_render_messages_mod = importlib.import_module(_src_pkg + '.proxy_display.render_messages')
_render_span_content = _render_messages_mod._render_span_content

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

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

# Real pass order from src/proxy/rules.py::apply_modification_rules — _passes list, then the
# _dedup_wakeup_blocks call that follows the loop. Each pass function is called with ONLY the
# per-request NEW message slice (see _scan_file) — legitimate because every pass here decides
# per-message from that message's own content alone (verified by reading message_passes.py: no
# pass reads any OTHER message's content), so feeding only new messages is equivalent to feeding
# the full growing list and produces identical per-message ops without dual-log's cumulative
# duplicate counting (same dedup principle as D1, blessed for that deliverable).
_PASSES = [
    _apply_role_system_strip,
    _apply_sn_notice_strip,
    _apply_first_pass,
    _apply_cumulative_sr_strips,
    _apply_final_sr_pass,
    _apply_po_preview_strip,
    _apply_bg_exit_strip,
    _apply_bg_launch_ack_strip,
    _apply_hook_prefix_strip,
    _apply_git_lock_strip,
    _apply_bd_noise_strip,
]

# Semantic classification per call site — determined by READING the underlying strip function,
# not by any measured ratio. FULL = new block content is constructed independently of the old
# (a fixed literal, or a freshly-derived string) with no attempt to preserve any of the old text
# outside what a template happens to share. PARTIAL = a known marker/chunk is excised from within
# the text (regex.sub / str.replace / slice) and everything else in the block is kept verbatim.
# STRUCTURAL = neither — an index-shift artifact, not a designed content transform.
PASS_CLASS = {
    '_apply_role_system_strip': (
        'FULL',
        "message_passes.py:66 — result.append({**msg, 'content': '.'}) — content set to the "
        "literal '.' independent of old content"),
    '_apply_sn_notice_strip': (
        'PARTIAL',
        "strip_sn_notice.py:66 — text.replace(needle, '', 1) — paragraph excised, remainder kept"),
    '_apply_cumulative_sr_strips': (
        'PARTIAL',
        "strip_sr.py:138 (via _strip_system_reminder) — _STANDALONE_SR_RE.sub(_replace, text) — "
        "matched SR block(s) excised, remainder kept"),
    '_apply_final_sr_pass': (
        'PARTIAL',
        "strip_sr.py:138 (via _strip_all_system_reminders) — same regex-sub excise mechanism"),
    '_apply_po_preview_strip': (
        'PARTIAL',
        "strip_po.py:72 — _PO_PREVIEW_RE.sub(_replace, text) — only the 'preview' capture group "
        "is dropped, 'open'+'close' groups (and everything outside the match) kept"),
    '_apply_bg_exit_strip': (
        'PARTIAL',
        "strip_bg_completed.py:68 — _BG_EXIT_RE.sub(_replace, text) — matched notification line(s) "
        "excised/replaced in place, remainder kept"),
    '_apply_bg_launch_ack_strip': (
        'FULL',
        "strip_bg_launch_ack.py:44/57/65/76 — block text/content field set wholesale to "
        "_build_launch_ack_replacement(text), independent of old text (anchored block-initial "
        "match only, but ANY trailing content after the ack in that block is also discarded)"),
    '_apply_hook_prefix_strip': (
        'PARTIAL',
        "strip_hook_prefix.py:68 — _HOOK_PREFIX_RE.sub(_replace, text, count=1) — prefix excised, "
        "remainder kept"),
    '_apply_git_lock_strip': (
        'PARTIAL',
        "strip_git_lock.py:70 — text.replace(needle, '', 1) — advice block excised, remainder kept"),
    '_apply_bd_noise_strip': (
        'PARTIAL',
        "strip_bd_noise.py:91 — _BD_NOISE_RE.sub(_collect, text) — matched noise line(s) excised, "
        "remainder kept"),
    '_dedup_wakeup_blocks:str': (
        'PARTIAL',
        "message_passes.py:105 — new_content_str = content[:end] — prefix-preserving truncation, "
        "kept prefix IS the remainder"),
    '_dedup_wakeup_blocks:list': (
        'STRUCTURAL',
        "message_passes.py:88-96 — drops a duplicate BLOCK from the content list; later blocks "
        "shift index, so _ops_from_content_change compares UNRELATED blocks positionally at the "
        "shifted index (index-shift artifact, not a designed content replacement)"),
}

# _apply_first_pass is one function with 5 internal elif-branches, each with a DIFFERENT
# classification — sub-classify per message by re-evaluating the same branch conditions the
# real function uses (reusing the real predicate functions, not reimplementing their logic)
FIRST_PASS_BRANCH_CLASS = {
    'TN': ('PARTIAL',
           "payload_helpers.py:159 — _NOTIF_PAT.sub(_repl, content) or '.' — regex splice, "
           "preserves any surrounding text; falls back to '.' only if nothing remains"),
    'task_tools_nag': ('PARTIAL', "strip_sr.py:138 via _strip_system_reminder"),
    'deferred_tools': ('PARTIAL', "strip_sr.py:138 via _strip_system_reminder"),
    'user_interrupt': ('PARTIAL',
                        "strip_sr.py:134-136 — 'partial' template mode: IMPORTANT line excised, "
                        "user body + outer tags preserved"),
    'rejection': ('FULL',
                  "content_strip.py:31 (str) / :43 (tool_result block) — content set to the "
                  "literal '.' independent of old content"),
}


# FUNCTIONS

# Re-derive which _apply_first_pass elif-branch fires for one message — mirrors the real
# elif-chain in message_passes.py exactly, reusing the real predicate functions
def _first_pass_branch(old_content, role):
    if role in ('user', 'system') and _top_level_content_contains(old_content, '<task-notification>'):
        return 'TN'
    if role == 'user' and _top_level_content_contains(old_content, 'task tools haven'):
        return 'task_tools_nag'
    if role == 'user' and _top_level_content_contains(old_content, 'deferred tools are now available via ToolSearch'):
        return 'deferred_tools'
    if role == 'user' and _top_level_content_contains(old_content, 'user sent a new message while you were working'):
        return 'user_interrupt'
    if role == 'user' and _message_has_rejection(old_content):
        return 'rejection'
    return None


# Block text at blk_idx, mirroring _ops_from_content_change's own extraction exactly
def _block_text(content, blk_idx):
    if isinstance(content, list):
        return _block_inner_text(content[blk_idx]) if blk_idx < len(content) else ''
    if isinstance(content, str):
        return content
    return ''


# Drive one delta message-list through all passes in real order, collecting every op with its
# semantic class + evidence + (bt, at) for corroborating-ratio + render reproduction
def _drive_passes(delta_messages, records):
    new_messages = delta_messages
    for pass_fn in _PASSES:
        messages_before = new_messages
        new_messages, _mods, _removed, c_idxs, _injected, pass_ops = pass_fn(messages_before)
        for msg_idx, blk_map in pass_ops.items():
            role = messages_before[msg_idx].get('role', '?')
            old_content = messages_before[msg_idx].get('content', '')
            new_content = new_messages[msg_idx].get('content', '')
            if pass_fn.__name__ == '_apply_first_pass':
                branch = _first_pass_branch(old_content, role)
                site = f'_apply_first_pass:{branch}'
                cls, evidence = FIRST_PASS_BRANCH_CLASS.get(branch, ('UNKNOWN', 'branch not resolved'))
            else:
                site = pass_fn.__name__
                cls, evidence = PASS_CLASS[site]
            for blk_idx, op_list in blk_map.items():
                bt = _block_text(old_content, blk_idx)
                at = _block_text(new_content, blk_idx)
                for (offset, removed, injected) in op_list:
                    records.append({
                        'site': site, 'class': cls, 'evidence': evidence,
                        'offset': offset, 'removed': removed, 'injected': injected,
                        'bt': bt, 'at': at,
                    })
    # _dedup_wakeup_blocks runs after the pass loop in rules.py, outside _passes
    messages_before = new_messages
    new_messages, pass_ops = _dedup_wakeup_blocks(new_messages)
    for msg_idx, blk_map in pass_ops.items():
        old_content = messages_before[msg_idx].get('content', '')
        new_content = new_messages[msg_idx].get('content', '')
        shape = 'list' if isinstance(old_content, list) else 'str'
        site = f'_dedup_wakeup_blocks:{shape}'
        cls, evidence = PASS_CLASS[site]
        for blk_idx, op_list in blk_map.items():
            bt = _block_text(old_content, blk_idx)
            at = _block_text(new_content, blk_idx)
            for (offset, removed, injected) in op_list:
                records.append({
                    'site': site, 'class': cls, 'evidence': evidence,
                    'offset': offset, 'removed': removed, 'injected': injected,
                    'bt': bt, 'at': at,
                })
    return new_messages


# Scan one corpus file: dedup via prev-message-count delta (same principle as D1) — each pass
# function decides per-message from that message's own content alone (no cross-message
# dependency in any of the 11 passes, verified by reading message_passes.py), so feeding only
# the newly-introduced messages per request reproduces the exact same per-message ops the real
# cumulative pipeline would produce, without reprocessing (and over-counting) duplicated history.
def _scan_file(path, records):
    prev_count = 0
    requests = 0
    with open(path, 'rb') as fh:
        for raw in fh:
            requests += 1
            entry = json.loads(raw)
            messages = entry.get('payload', {}).get('messages', [])
            start = prev_count if prev_count <= len(messages) else 0
            delta = messages[start:]
            if delta:
                _drive_passes(delta, records)
            prev_count = len(messages)
    return requests


def _trimmed(rec):
    bt = rec['bt']
    s = len(bt) - rec['offset'] - len(rec['removed'])
    return rec['offset'] > 0 or s > 0


def _ratio(rec):
    bt = rec['bt']
    return (len(rec['removed']) / len(bt)) if bt else None


def _dist(values):
    if not values:
        return None
    values = sorted(values)
    return {
        'n': len(values), 'min': values[0], 'max': values[-1],
        'median': statistics.median(values),
        'mean': round(statistics.mean(values), 3),
    }


# Render one op through the REAL compose_block + _render_span_content pipeline — "recorded"
# uses today's actual op (possibly prefix/suffix-trimmed); "hypothetical" uses a synthetic
# full-block op (0, bt, at) to show how a full-replacement-aware _extract_block_op would render
# the SAME underlying change. Returns (recorded_lines, hypothetical_lines), ANSI stripped.
def _render_comparison(rec):
    bt = rec['bt']
    recorded_op = [(rec['offset'], rec['removed'], rec['injected'])]
    hypothetical_op = [(0, bt, rec['at'])]

    def _lines_for(ops):
        spans = compose_block(bt, ops)
        s_texts = [t for tag, t in spans if tag == 'stripped' and t]
        i_spans = [(tag, t) for tag, t in spans if tag in ('equal', 'injected') and t]
        lines, _keys = _render_span_content('', i_spans, s_texts, '      ')
        return [_ANSI_RE.sub('', ln) for ln in lines]

    return _lines_for(recorded_op), _lines_for(hypothetical_op)


# Build the markdown report
def _build_report(records, total_requests):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines.append('# D2 — full-replacement blast-radius measurement for `_extract_block_op`')
    lines.append('')
    lines.append(f'Generated: {ts}')
    lines.append('')
    lines.append('## Corpus')
    lines.append('')
    lines.append('| File | Included | Notes |')
    lines.append('|---|---|---|')
    for fname in CORPUS_FILES:
        lines.append(f'| `{fname}` | yes | |')
    for fname, reason in EXCLUDED_FILES.items():
        lines.append(f'| `{fname}` | **excluded** | {reason} |')
    lines.append('')
    lines.append(f'Total requests scanned (deduped, new-messages-only pass): {total_requests}')
    lines.append(f'Total ops captured across all 17 call sites: {len(records)}')
    lines.append('')
    lines.append(
        '## Method — classification is SEMANTIC (per call site), not a len(removed)/len(bt) threshold'
    )
    lines.append('')
    lines.append(
        'Each of the 17 `_ops_from_content_change` call sites was classified by reading its underlying '
        'strip function: **FULL** = new block content is constructed independently of the old (a fixed '
        'literal or a freshly-derived string, with no attempt to preserve surrounding text). **PARTIAL** '
        '= a known marker/chunk is excised from within the text (regex.sub / str.replace / slice) and '
        'everything else in the block is kept verbatim. **STRUCTURAL** = neither (index-shift artifact). '
        'The `len(removed)/len(bt)` ratio is reported below only as corroborating evidence.'
    )
    lines.append('')
    lines.append('| Call site | Class | Evidence |')
    lines.append('|---|---|---|')
    for site, (cls, ev) in PASS_CLASS.items():
        lines.append(f'| `{site}` | {cls} | {ev} |')
    for branch, (cls, ev) in FIRST_PASS_BRANCH_CLASS.items():
        lines.append(f'| `_apply_first_pass:{branch}` | {cls} | {ev} |')
    lines.append('')

    by_site = defaultdict(list)
    for r in records:
        by_site[r['site']].append(r)

    lines.append('## Per-pass op counts (PARTIAL / FULL / STRUCTURAL) — all 17 call sites, 0-count stated plainly')
    lines.append('')
    lines.append('| Call site | Class | Ops | Ops with bt=="" (insert, no defect exposure) |')
    lines.append('|---|---|---|---|')
    all_sites = {**PASS_CLASS, **{f'_apply_first_pass:{b}': c for b, c in FIRST_PASS_BRANCH_CLASS.items()}}
    for site in sorted(all_sites, key=lambda s: -len(by_site.get(s, []))):
        recs = by_site.get(site, [])
        cls = all_sites[site][0]
        n_insert = sum(1 for r in recs if not r['bt'])
        lines.append(f'| `{site}` | {cls} | {len(recs)} | {n_insert} |')
    lines.append('')
    lines.append(
        '**Why so many PARTIAL sites show 0 ops in this corpus:** `_apply_role_system_strip` runs '
        'FIRST in the real pipeline and wholesale-replaces the ENTIRE content of every role=\'system\' '
        'message with `.` (unless it carries a `<task-notification>` tag). Several markers designed to '
        'be excised by later, genuinely-PARTIAL passes (`deferred tools are now available`, `task tools '
        'haven\'t been used`, skills/agent-types/claudeMd SR blocks) arrive on role=\'system\' messages '
        'in this corpus and are consumed wholesale by `_apply_role_system_strip` before '
        '`_apply_cumulative_sr_strips` / `_apply_first_pass`\'s nag branches ever see them — by the time '
        'those later passes run, content is already `.` and `_top_level_content_contains` fails. This is '
        'a corpus characteristic (all measured occurrences of these markers happened to be role=\'system\'), '
        'not evidence those passes are unreachable in general — see the "other FULL site" render example '
        'below, which shows exactly this content (deferred-tools + agent-types + skills text) arriving on '
        'a role=\'system\' message and getting the wholesale-`.` treatment instead.'
    )
    lines.append('')

    full_recs = [r for r in records if r['class'] == 'FULL' and r['bt']]
    partial_recs = [r for r in records if r['class'] == 'PARTIAL' and r['bt']]
    struct_recs = [r for r in records if r['class'] == 'STRUCTURAL' and r['bt']]

    lines.append('## Blast radius — FULL replacements currently recorded as a trimmed (partial-looking) span')
    lines.append('')
    full_trimmed = [r for r in full_recs if _trimmed(r)]
    lines.append(f'FULL-class ops: **{len(full_recs)}**. Of those, currently trimmed (offset>0 or suffix trimmed — '
                  f'would render as a 2-piece split today, would become one contiguous span under a '
                  f'full-replacement-aware `_extract_block_op`): **{len(full_trimmed)}**.')
    lines.append('')
    lines.append('| Call site | FULL ops | trimmed (offset>0 or suffix>0) |')
    lines.append('|---|---|---|')
    for site in sorted(set(r['site'] for r in full_recs)):
        site_full = [r for r in full_recs if r['site'] == site]
        site_trimmed = [r for r in site_full if _trimmed(r)]
        lines.append(f'| `{site}` | {len(site_full)} | {len(site_trimmed)} |')
    lines.append('')

    lines.append('## Flagged edge case — empty-injected-span when the "." replacement is absorbed as a common suffix')
    lines.append('')
    lines.append(
        "For FULL sites whose replacement is the literal `'.'` (`_apply_role_system_strip`, "
        "`_apply_first_pass:rejection`), if the ORIGINAL block text also happens to end in `.`, the "
        "single-char injected `.` gets absorbed entirely as the common SUFFIX by `_extract_block_op` "
        "— the recorded op then has an EMPTY `injected` string, so the pane shows the stripped (yellow) "
        "text with NO green replacement line at all, not even the collapsed marker."
    )
    lines.append('')
    dot_sites = [r for r in full_recs if r['at'] == '.']
    dot_absorbed = [r for r in dot_sites if r['bt'].endswith('.') and r['injected'] == '']
    lines.append(f'Ops with `at == "."`: **{len(dot_sites)}**. Of those, with original text ending in `.` AND '
                  f'injected fully absorbed (empty): **{len(dot_absorbed)}**.')
    lines.append('')

    lines.append('## Corroborating evidence — len(removed)/len(bt) ratio distribution per class')
    lines.append('')
    lines.append('| Class | n | min | median | mean | max |')
    lines.append('|---|---|---|---|---|---|')
    for label, recs in (('FULL', full_recs), ('PARTIAL', partial_recs), ('STRUCTURAL', struct_recs)):
        d = _dist([_ratio(r) for r in recs])
        if d is None:
            lines.append(f'| {label} | 0 | — | — | — | — |')
        else:
            lines.append(f'| {label} | {d["n"]} | {d["min"]:.3f} | {d["median"]:.3f} | {d["mean"]:.3f} | {d["max"]:.3f} |')
    lines.append('')
    full_ratios = [_ratio(r) for r in full_recs]
    partial_ratios = [_ratio(r) for r in partial_recs]
    overlap = (
        bool(full_ratios) and bool(partial_ratios)
        and min(full_ratios) <= max(partial_ratios)
        and max(full_ratios) >= min(partial_ratios)
    )
    if overlap:
        lines.append(
            f'**Ranges OVERLAP** — FULL ratios span [{min(full_ratios):.3f}, {max(full_ratios):.3f}], '
            f'PARTIAL ratios span [{min(partial_ratios):.3f}, {max(partial_ratios):.3f}]. Confirms a fixed '
            f'ratio threshold would misclassify: some PARTIAL excisions remove a large fraction of a small '
            f'surrounding block, and/or some FULL replacements share enough incidental text with the '
            f'original to score a low ratio. This is why classification is per-call-site/semantic, not '
            f'ratio-based.'
        )
    elif full_ratios and partial_ratios:
        lines.append(
            f'Ranges separate cleanly: FULL ratios span [{min(full_ratios):.3f}, {max(full_ratios):.3f}], '
            f'PARTIAL ratios span [{min(partial_ratios):.3f}, {max(partial_ratios):.3f}] — the measured '
            f'boundary in this corpus (informational only, not used anywhere in the classification logic).'
        )
    lines.append('')

    lines.append('## Structural (index-shift) sites — `_dedup_wakeup_blocks:list`')
    lines.append('')
    lines.append(f'Ops observed: **{len(struct_recs)}**.')
    if struct_recs:
        lines.append('(present in corpus — see per-pass table above for count; not folded into FULL/PARTIAL)')
    else:
        lines.append('0 occurrences in this corpus — reported plainly, not manufactured.')
    lines.append('')

    lines.append('## Concrete rendered before/after — real `compose_block` + `_render_span_content`')
    lines.append('')

    def _pick(predicate, pool):
        for r in pool:
            if predicate(r):
                return r
        return None

    examples = []
    bg_ack = _pick(lambda r: r['site'] == '_apply_bg_launch_ack_strip' and _trimmed(r), full_recs)
    if bg_ack:
        examples.append(('bg-launch-ack (FULL, trimmed — defect B flagship case)', bg_ack))
    dot_example = _pick(lambda r: r in dot_absorbed, full_recs) if dot_absorbed else None
    if dot_example:
        examples.append(("'.' replacement fully absorbed as suffix (FULL, empty injected)", dot_example))
    other_full = _pick(lambda r: r['site'] != '_apply_bg_launch_ack_strip' and r is not dot_example, full_recs)
    if other_full:
        examples.append(('other FULL site', other_full))
    # Prefer a PARTIAL op that IS trimmed (offset>0 or suffix trimmed) with ratio<1 — shows
    # trimming is CORRECT/desirable there (excises a marker, keeps real surrounding text),
    # unlike the FULL sites above where trimming is the defect.
    trimmed_partial = _pick(lambda r: _trimmed(r) and (_ratio(r) or 0) < 0.95, partial_recs)
    if trimmed_partial:
        examples.append(('PARTIAL, trimmed — correctly served by trimming (contrast case)', trimmed_partial))
    elif partial_recs:
        examples.append(('PARTIAL (highest removed-fraction available)',
                          max(partial_recs, key=lambda r: _ratio(r) or 0)))

    for label, rec in examples:
        lines.append(f'### {label}')
        lines.append('')
        r_ratio = _ratio(rec)
        lines.append(f'Site: `{rec["site"]}` | ratio={r_ratio:.3f} '
                      f'| offset={rec["offset"]} | trimmed={_trimmed(rec)}')
        lines.append('')
        lines.append('Original block text:')
        lines.append('```')
        lines.append(rec['bt'][:500])
        lines.append('```')
        lines.append('Forwarded (after) block text:')
        lines.append('```')
        lines.append(rec['at'][:500])
        lines.append('```')
        recorded_lines, hyp_lines = _render_comparison(rec)
        lines.append('')
        lines.append('**Pane render TODAY (recorded op, ANSI stripped):**')
        lines.append('```')
        lines.extend(recorded_lines[:40])
        lines.append('```')
        lines.append('**Pane render under a full-replacement-aware op (hypothetical, ANSI stripped):**')
        lines.append('```')
        lines.extend(hyp_lines[:40])
        lines.append('```')
        lines.append('')

    return '\n'.join(lines)


# ORCHESTRATOR
def main():
    records = []
    total_requests = 0
    for fname in CORPUS_FILES:
        path = LOG_DIR / fname
        print(f'scanning {fname} ...')
        total_requests += _scan_file(path, records)
    report = _build_report(records, total_requests)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / 'full_replacement_blast_radius_20260729.md'
    out_path.write_text(report, encoding='utf-8')
    print(f'wrote {out_path} — {len(records)} ops captured, {total_requests} requests scanned')


if __name__ == '__main__':
    main()
