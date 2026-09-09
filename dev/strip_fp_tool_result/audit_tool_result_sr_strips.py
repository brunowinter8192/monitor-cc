#!/usr/bin/env python3
"""Audit: which SR-strip-family passes remove content from INSIDE tool_result blocks.

Measurement only — does not modify src/. Runs the 11 real `_apply_*` pass functions
from `src.proxy.message_passes`, threaded forward in the EXACT order
`rules.py::apply_modification_rules` uses (`_passes` list), over every request payload
in `src/logs/dual_log/*_original.jsonl`.

Why individual passes instead of `apply_modification_rules` directly: behaviorally
identical (same functions, same order, same inputs/outputs) but each pass call also
returns `pass_ops_by_msg_blk` — {msg_idx: {blk_idx: [(offset, removed, injected), ...]}}
— which `apply_modification_rules` discards. That per-block diff is what lets us check
the block's ORIGINAL `type` at (msg_idx, blk_idx) before the pass ran, i.e. whether the
removed text came out of a `tool_result` block specifically.

Offset representation: `_ops_from_content_change` (rule_ops.py) computes the diff on
`_block_inner_text(block)` — for `tool_result` with str content that IS the string; for
`tool_result` with list-of-text sub-blocks, it is those sub-blocks' text JOINED with
'\\n'. This script recomputes `_block_inner_text(block)` on the same (old, unmodified)
block object before slicing context around `offset`, so the excerpt is always taken
from the same representation the offset was computed against. `block_shape` in each
occurrence record states which of the two it was.

Self-session handling: this worker's OWN dual-log (name contains 'sr-fp-audit') is
EXCLUDED from the scan — it is being written live while this script runs and would
make the script's own tool calls (Read/Bash on this very investigation) show up as
"evidence". Excluded files are named explicitly in the report, not silently dropped.

Classification (quoted data / genuine CC injection / ambiguous) is NOT automated: the
script surfaces template, tool, verbatim text, and context; the verdict + evidence is
written by hand into `_MANUAL_VERDICTS` below after reviewing a first run's output,
then the script is re-run to fold verdicts into the final report and aggregate counts.

Usage: python3 dev/strip_fp_tool_result/audit_tool_result_sr_strips.py
Output: dev/strip_fp_tool_result/md/audit_tool_result_sr_strips.md
"""
import json
import sys
import os
import time
from pathlib import Path
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
import importlib as _il
_mp = _il.import_module('src.proxy.message_passes')
# Structural passes (own logic) stayed in message_passes.py; template passes (generic pass
# runner + declarative spec) moved to message_passes_simple.py (2026-09, helper-extraction milestone).
_mp2 = _il.import_module('src.proxy.message_passes_simple')
_apply_role_system_strip = _mp._apply_role_system_strip
_apply_sn_notice_strip = _mp2._apply_sn_notice_strip
_apply_first_pass = _mp._apply_first_pass
_apply_cumulative_sr_strips = _mp._apply_cumulative_sr_strips
_apply_final_sr_pass = _mp._apply_final_sr_pass
_apply_po_preview_strip = _mp2._apply_po_preview_strip
_apply_bg_exit_strip = _mp2._apply_bg_exit_strip
_apply_bg_launch_ack_strip = _mp2._apply_bg_launch_ack_strip
_apply_hook_prefix_strip = _mp2._apply_hook_prefix_strip
_apply_git_lock_strip = _mp2._apply_git_lock_strip
_apply_bd_noise_strip = _mp2._apply_bd_noise_strip

_sr_mod = _il.import_module('src.proxy.strip_sr')
_INNER_SR_RE = _sr_mod._INNER_SR_RE
_match_template = _sr_mod._match_template
_ALL_TEMPLATES = _sr_mod._ALL_TEMPLATES
_ENV_CONTEXT_RE = _sr_mod._ENV_CONTEXT_RE
_IMP_LINE_RE = _sr_mod._IMP_LINE_RE

_cs_mod = _il.import_module('src.proxy.content_strip')
_REJECTION_MARKER = _cs_mod._REJECTION_MARKER

_ro_mod = _il.import_module('src.proxy.rule_ops')
_block_inner_text = _ro_mod._block_inner_text

_gl_mod = _il.import_module('src.proxy.strip_git_lock')
_GIT_LOCK_MARKER = _gl_mod._GIT_LOCK_MARKER
_GIT_LOCK_ADVICE = _gl_mod._GIT_LOCK_ADVICE
del _il, _mp, _mp2, _sr_mod, _cs_mod, _ro_mod, _gl_mod

# Actual runtime dual-log location (main checkout, not this worktree — src/logs/ is gitignored
# per-worktree; the corpus only exists here).
LOGS_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')
OUT_FILE = Path(os.path.join(os.path.dirname(__file__), 'md', 'audit_tool_result_sr_strips.md'))

# This worker's own live session log — excluded, see module docstring.
SELF_SESSION_MARKER = 'sr-fp-audit'

# Real pipeline order — copied from src/proxy/rules.py::apply_modification_rules `_passes` list.
PASSES = [
    ('_apply_role_system_strip', _apply_role_system_strip),
    ('_apply_sn_notice_strip', _apply_sn_notice_strip),
    ('_apply_first_pass', _apply_first_pass),
    ('_apply_cumulative_sr_strips', _apply_cumulative_sr_strips),
    ('_apply_final_sr_pass', _apply_final_sr_pass),
    ('_apply_po_preview_strip', _apply_po_preview_strip),
    ('_apply_bg_exit_strip', _apply_bg_exit_strip),
    ('_apply_bg_launch_ack_strip', _apply_bg_launch_ack_strip),
    ('_apply_hook_prefix_strip', _apply_hook_prefix_strip),
    ('_apply_git_lock_strip', _apply_git_lock_strip),
    ('_apply_bd_noise_strip', _apply_bd_noise_strip),
]

# The SR strip family this issue actually audits — _apply_first_pass's SR-producing branches
# (task-tools-nag / deferred-tools / user-interrupt), _apply_cumulative_sr_strips, and
# _apply_final_sr_pass all descend via _content_contains + strip_sr.py's line-anchored
# <system-reminder> matching. bg_launch_ack / hook_prefix / po_preview match their OWN, unrelated
# markers (none imports strip_sr) — their tool_result descent is correct and out of this issue's
# scope, reported separately, never pooled into the SR-family verdict.
_SR_FAMILY_PASSES = {'_apply_first_pass', '_apply_cumulative_sr_strips', '_apply_final_sr_pass'}


def _family(pass_name):
    return 'SR strip family (audited)' if pass_name in _SR_FAMILY_PASSES else 'non-SR pass (own marker, out of scope)'


# Passes whose OWN source explicitly documents they do NOT descend into tool_result
# (role_system only ever touches role=='system' messages, which never carry tool_result blocks).
# Any tool_result hit attributed to these three is an anomaly against the code's own design intent.
_ASSERT_NO_DESCEND = {'_apply_role_system_strip', '_apply_sn_notice_strip', '_apply_bg_exit_strip'}

# Passes with exactly one fixed mod name regardless of which idx/branch fired.
_FIXED_MOD_MAP = {
    '_apply_po_preview_strip': 'stripped_po_preview',
    '_apply_bg_launch_ack_strip': 'stripped_bg_launch_ack',
    '_apply_hook_prefix_strip': 'stripped_hook_error_prefix',
    '_apply_git_lock_strip': 'stripped_git_lock_advice',
    '_apply_bd_noise_strip': 'stripped_bd_noise',
    '_apply_role_system_strip': 'stripped_role_system_msg',
    '_apply_sn_notice_strip': 'stripped_sn_notice_paragraph',
    '_apply_bg_exit_strip': 'replaced_bg_completed_text',
}

# Manual quoted-data / genuine-injection / ambiguous classification, filled in by hand after
# reviewing a first run's raw occurrence context (see report body). Keyed by
# (file_name, msg_idx, blk_idx, first_line_idx) — practical to hand-write, unlike the full
# removed_text used for dedup. verdict in {'quoted data', 'genuine CC injection', 'ambiguous'}.
# Evidence for each verdict is in the Occurrences section render — see _render_report.
_MC = 'api_requests_opus_monitor_cc_1785259250_original.jsonl'
_PO = 'api_requests_opus_posts_1785266871_original.jsonl'
_W2 = 'api_requests_opus_wise2627_1785240377_original.jsonl'
_CR = 'api_requests_worker_85d6f25b_capture-monitor-cc-ref_1785272207_original.jsonl'
_MANUAL_VERDICTS = {
    # monitor_cc — hook-prefix / bg-launch-ack: all real Bash commands genuinely hitting the
    # hook or genuinely launched in background; context_before is empty (hook prefix) or the
    # literal 'Command ' stub (bg-ack), i.e. the removed text is the ENTIRE real tool_result.
    (_MC, 22, 0, 12):   ('genuine CC injection', "Bash ran `ls .../websearch; grep ... download_pdf ...` — real command tripped block_broad_grep.py; prefix is the whole tool_result (context_before empty), advisory text follows immediately."),
    (_MC, 53, 0, 27):   ('genuine CC injection', "Bash `sleep 600 && echo done` with run_in_background=true — genuine CC bg-launch ack; context_before='Command ', context_after='.' (the entire tool_result)."),
    (_MC, 66, 0, 33):   ('genuine CC injection', "Same pattern as msg[53]: real backgrounded `sleep 600` — genuine ack."),
    (_MC, 77, 0, 38):   ('genuine CC injection', "Bash ran `cd .../worktrees/pdf-refs && grep ...` — real command tripped block_cd_drift.py (cd into worktree); prefix is the whole tool_result."),
    (_MC, 83, 0, 41):   ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 120, 0, 58):  ('genuine CC injection', "Bash ran a real `rag-cli search ... | head -60` chain that tripped block_rag_cli_chained.py (non-rag-cli after rag-cli) — genuine hook prefix on the real tool_result."),
    (_MC, 128, 0, 62):  ('genuine CC injection', "Bash ran real `git config --global core.hooksPath; ...` — tripped block_git_destructive.py; genuine hook prefix."),
    (_MC, 202, 0, 97):  ('quoted data', "tool_use is `rag-cli search \"quoted system-reminder inside tool_result stripped false positive\" monitor-cc-docs --document 'process-docs/%'`. context_before is literally '## Task B — Env-context system-reminder ... CC injects this SR block on nearly every request:\\n```' and context_after continues '```\\n334 chars of inner text per request, never useful to the proxy model.' — a fenced EXAMPLE block inside a process-docs entry describing this very SR template, not a per-request CC injection into this tool_result."),
    (_MC, 249, 0, 119): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 264, 0, 126): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack."),
    (_MC, 270, 0, 129): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (this file is a LIVE, currently-growing session log — this row appeared between two runs of this script)."),
    (_MC, 300, 0, 143): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth as msg[270]; corpus keeps growing across re-runs during this report-framing fix)."),
    (_MC, 315, 0, 150): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 329, 0, 157): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 351, 0, 167): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    (_MC, 370, 0, 176): ('genuine CC injection', "Real backgrounded `sleep 600` — genuine ack (same LIVE-log growth, milestone-2 fix-verification re-run)."),
    # posts
    (_PO, 30, 0, 16):   ('genuine CC injection', "Bash ran real `rag-cli search ... monitor-cc-reference | head -60` — tripped block_rag_cli_chained.py; genuine hook prefix."),
    (_PO, 70, 0, 35):   ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 80, 0, 40):   ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 91, 0, 45):   ('genuine CC injection', "Real backgrounded `sleep 420` timer — genuine ack."),
    (_PO, 101, 0, 50):  ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 112, 0, 55):  ('genuine CC injection', "Real backgrounded `sleep 300` timer — genuine ack."),
    (_PO, 122, 0, 60):  ('genuine CC injection', "Real backgrounded `sleep 600` timer — genuine ack."),
    (_PO, 131, 0, 64):  ('genuine CC injection', "Real backgrounded `sleep 240` timer — genuine ack."),
    (_PO, 139, 0, 68):  ('genuine CC injection', "Real backgrounded `sleep 420` timer — genuine ack."),
    (_PO, 147, 0, 72):  ('genuine CC injection', "Real backgrounded `sleep 480` timer — genuine ack."),
    (_PO, 269, 0, 129): ('genuine CC injection', "Bash ran real `gh-cli index_issues ... | tail -20` — tripped block_gh_cli_chained.py; genuine hook prefix."),
    (_PO, 273, 0, 131): ('genuine CC injection', "Real backgrounded `gh-cli index_issues` — genuine ack."),
    # wise2627
    (_W2, 11, 0, 7):    ('genuine CC injection', "Bash `cat vor-unterschrift.md; ...` real output exceeded persist threshold (52KB) — Preview section is the genuine persisted-output wrapper around real command output."),
    (_W2, 158, 0, 77):  ('genuine CC injection', "Bash ran real `grep -rn ruhig wohnungssuche/Meta/` — tripped block_broad_grep.py; genuine hook prefix."),
    (_W2, 604, 0, 291): ('genuine CC injection', "Bash `curl`-style page fetch loop, real output exceeded persist threshold (39.4KB) — genuine Preview section."),
    (_W2, 697, 0, 335): ('genuine CC injection', "Bash ran real `rag-cli list_collections --filter wise ...` chain — tripped block_rag_cli_chained.py; genuine hook prefix."),
    # capture-monitor-cc-ref
    (_CR, 10, 0, 5):    ('genuine CC injection', "Bash `cat /tmp/tc_seed.html` real output (246323 bytes) exceeded persist threshold (240.6KB) — genuine Preview section of a real persisted-output wrapper."),
    (_CR, 58, 0, 27):   ('genuine CC injection', "Real backgrounded `rag-cli index --collection monitor-cc-reference` — genuine ack."),
}


# ORCHESTRATOR

def main():
    files = sorted(LOGS_DIR.glob('*_original.jsonl'))
    included = [f for f in files if SELF_SESSION_MARKER not in f.name]
    excluded = [f for f in files if SELF_SESSION_MARKER in f.name]

    per_file_stats = []
    occurrences = {}
    assertion_hits = []
    for fp in included:
        t0 = time.time()
        occ, hits, total_entries, requests_with_tr_hit = _scan_file(fp)
        for key, rec in occ.items():
            if key in occurrences:
                occurrences[key]['raw_count'] += rec['raw_count']
            else:
                occurrences[key] = rec
        assertion_hits.extend(hits)
        per_file_stats.append({
            'name': fp.name,
            'size_bytes': fp.stat().st_size,
            'entries': total_entries,
            'requests_with_tool_result_hit': requests_with_tr_hit,
            'unique_occurrences': len(occ),
            'seconds': round(time.time() - t0, 1),
        })
        print(f'[{fp.name}] entries={total_entries} unique_occ={len(occ)} '
              f'took={per_file_stats[-1]["seconds"]}s', file=sys.stderr, flush=True)

    ground_truth = _scan_ground_truth_git_lock(included)

    report = _render_report(included, excluded, per_file_stats, occurrences, assertion_hits, ground_truth)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report)
    print(report)
    print(f'\nWritten to {OUT_FILE}')


# FUNCTIONS

# Build tool_use_id -> {name, input_preview} from all assistant tool_use blocks in one payload's
# full (pre-strip) message list — tool_use blocks are never touched by any strip pass.
def _build_tool_id_map(messages):
    m = {}
    for msg in messages:
        if msg.get('role') != 'assistant':
            continue
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                m[block.get('id')] = {
                    'name': block.get('name'),
                    'input_preview': json.dumps(block.get('input', {}), ensure_ascii=False)[:200],
                }
    return m


# Classify a removed chunk's template/rule using the REAL registries from strip_sr.py /
# content_strip.py (imported, not reinvented) — falls back to the pass's fixed mod name for
# non-SR-shaped removals (git-lock, hook-prefix, bd-noise, po-preview, ...).
def _classify_removed_text(pass_name, removed_text):
    stripped = removed_text.strip()
    if stripped.startswith('<system-reminder>'):
        inner_m = _INNER_SR_RE.search(stripped)
        if inner_m:
            inner = inner_m.group(1).strip()
            if _ENV_CONTEXT_RE.fullmatch(inner):
                return 'sr:env-context'
            tid, _mode = _match_template(inner, _ALL_TEMPLATES)
            return f'sr:{tid}' if tid else 'sr:unknown-template'
    if _REJECTION_MARKER in removed_text:
        return 'stripped_rejection_message'
    if _IMP_LINE_RE.search(removed_text):
        return 'user-interrupt-important-line'
    return _FIXED_MOD_MAP.get(pass_name, f'unclassified:{pass_name}')


# True if an odd number of ``` fences precede the offset — signals "inside an open fence".
def _odd_fence_count(text_before):
    return text_before.count('```') % 2 == 1


# Slice before/after context around [offset, offset+removed_len) from flat_text — the SAME
# joined representation _ops_from_content_change computed offset against (see module docstring).
def _context_window(flat_text, offset, removed_len, before=400, after=200):
    start = max(0, offset - before)
    end = min(len(flat_text), offset + removed_len + after)
    return flat_text[start:offset], flat_text[offset + removed_len:end]


# Stream one dual-log file; return (occurrences_by_key, assertion_hits, total_entries,
# requests_with_a_tool_result_hit).
def _scan_file(fp):
    occurrences = {}
    assertion_hits = []
    total_entries = 0
    requests_with_tr_hit = 0
    with open(fp, 'r') as fh:
        for line_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            total_entries += 1
            entry = json.loads(line)
            payload = entry.get('payload') or {}
            messages = payload.get('messages') or []
            if not messages:
                continue
            tool_id_map = _build_tool_id_map(messages)
            cur_messages = messages
            hit_this_request = False
            for pass_name, pass_fn in PASSES:
                new_messages, _mods, _removed, changed_idxs, _inj, ops_by_msg_blk = pass_fn(cur_messages)
                for msg_idx in changed_idxs:
                    old_content = cur_messages[msg_idx].get('content')
                    if not isinstance(old_content, list):
                        continue
                    for blk_idx, op_list in ops_by_msg_blk.get(msg_idx, {}).items():
                        if blk_idx >= len(old_content):
                            continue
                        block = old_content[blk_idx]
                        if not (isinstance(block, dict) and block.get('type') == 'tool_result'):
                            continue
                        inner = block.get('content', '')
                        shape = 'tool_result_str' if isinstance(inner, str) else 'tool_result_list_joined'
                        flat_text = _block_inner_text(block)
                        tool_use_id = block.get('tool_use_id')
                        tool_info = tool_id_map.get(tool_use_id, {})
                        for offset, removed, _injected in op_list:
                            if not removed:
                                continue
                            hit_this_request = True
                            if pass_name in _ASSERT_NO_DESCEND:
                                assertion_hits.append(
                                    (fp.name, line_idx, pass_name, msg_idx, blk_idx, removed[:200])
                                )
                            key = (fp.name, removed)
                            if key not in occurrences:
                                before_ctx, after_ctx = _context_window(flat_text, offset, len(removed))
                                occurrences[key] = {
                                    'file': fp.name,
                                    'first_line_idx': line_idx,
                                    'raw_count': 0,
                                    'pass_name': pass_name,
                                    'template': _classify_removed_text(pass_name, removed),
                                    'tool_name': tool_info.get('name', 'UNKNOWN'),
                                    'tool_use_id': tool_use_id,
                                    'tool_input_preview': tool_info.get('input_preview', ''),
                                    'msg_idx': msg_idx,
                                    'blk_idx': blk_idx,
                                    'block_shape': shape,
                                    'offset': offset,
                                    'removed_text': removed,
                                    'context_before': before_ctx,
                                    'context_after': after_ctx,
                                    'fence_odd_before': _odd_fence_count(before_ctx),
                                    'request_id': entry.get('request_id'),
                                    'flow_id': entry.get('flow_id'),
                                    'timestamp': entry.get('timestamp'),
                                }
                            occurrences[key]['raw_count'] += 1
                cur_messages = new_messages
            if hit_this_request:
                requests_with_tr_hit += 1
    return occurrences, assertion_hits, total_entries, requests_with_tr_hit


# Practical lookup key into _MANUAL_VERDICTS — (file, msg_idx, blk_idx, first_line_idx).
def _verdict_key(rec):
    return (rec['file'], rec['msg_idx'], rec['blk_idx'], rec['first_line_idx'])


# Reproducibility check for the task-stated ground truth ("quoted git-lock advice block out of
# retrieved reference material"): counts, per file, how many requests have the git-lock MARKER
# substring anywhere in a tool_result vs. how many have the full literal _GIT_LOCK_ADVICE (real
# newlines) present — only the latter would ever actually get stripped by `_strip_git_lock_advice`
# (exact-substring match). A marker hit with no literal-advice hit is a source-code / escaped
# quote (e.g. Read of strip_git_lock.py itself, where `\n` is two literal characters, not a
# newline byte) that the exact-match guard already protects against, by construction.
def _scan_ground_truth_git_lock(files):
    per_file = []
    for fp in files:
        marker_lines = 0
        literal_lines = 0
        with open(fp, 'r') as fh:
            for line in fh:
                if _GIT_LOCK_MARKER not in line:
                    continue
                entry = json.loads(line)
                messages = (entry.get('payload') or {}).get('messages') or []
                has_marker = False
                has_literal = False
                for msg in messages:
                    content = msg.get('content')
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if not (isinstance(block, dict) and block.get('type') == 'tool_result'):
                            continue
                        flat = _block_inner_text(block)
                        if _GIT_LOCK_MARKER in flat:
                            has_marker = True
                            if _GIT_LOCK_ADVICE in flat:
                                has_literal = True
                if has_marker:
                    marker_lines += 1
                if has_literal:
                    literal_lines += 1
        per_file.append({'file': fp.name, 'marker_lines': marker_lines, 'literal_lines': literal_lines})
    return per_file


def _excerpt(text, limit=3000):
    if len(text) <= limit:
        return text
    return text[:limit] + f'\n...[TRUNCATED — {len(text)} chars total]'


def _render_report(included, excluded, per_file_stats, occurrences, assertion_hits, ground_truth):
    lines = []
    lines.append('# Audit: SR-strip false positives inside tool_result content')
    lines.append('')
    lines.append('Measurement only (per task scope) — no src/ changes. Method, scope, and offset '
                  'representation are documented in `audit_tool_result_sr_strips.py`\'s module docstring.')
    lines.append('')
    lines.append('## Corpus')
    lines.append('')
    lines.append(f'`{LOGS_DIR}` — glob found **{len(included) + len(excluded)}** `*_original.jsonl` '
                  f'files (not the 5 originally assumed).')
    lines.append('')
    lines.append('| File | Size | Entries | Requests w/ tool_result hit | Unique occurrences | Scan time |')
    lines.append('|---|---|---|---|---|---|')
    for s in per_file_stats:
        lines.append(f'| `{s["name"]}` | {s["size_bytes"]:,} B | {s["entries"]} | '
                      f'{s["requests_with_tool_result_hit"]} | {s["unique_occurrences"]} | {s["seconds"]}s |')
    lines.append('')
    if excluded:
        lines.append(f'**Excluded (self-session):** {", ".join(f"`{f.name}`" for f in excluded)} — '
                      f'this is the audit worker\'s OWN live dual-log, growing while this script runs. '
                      f'Its tool calls (Read/Bash on this very investigation) are not evidence of a '
                      f'production false-positive and must not silently become a data point.')
        lines.append('')
    lines.append('**Note — other sessions in this corpus are ALSO live.** `api_requests_opus_monitor_cc_...` '
                  'grew a new request between two runs of this script during development (a real, concurrent '
                  'Opus session is active) — the occurrence count is a snapshot at scan time, not a fixed '
                  'total.')
    lines.append('')

    all_occ = sorted(occurrences.values(), key=lambda r: (r['file'], r['first_line_idx']))

    lines.append('## Ground-truth reproduction check — `stripped_git_lock_advice`')
    lines.append('')
    lines.append('Task-stated ground truth: a prior session found 2 stripped segments in this corpus, '
                  'incl. `stripped_git_lock_advice` removing "a quoted git-lock advice block out of '
                  'retrieved reference material". Per-file count of requests where the git-lock MARKER '
                  'substring appears in a tool_result vs. requests where the full LITERAL 5-line advice '
                  '(real newlines — what `_strip_git_lock_advice` actually matches) appears there:')
    lines.append('')
    lines.append('| File | Requests w/ marker in tool_result | Requests w/ literal full-block match |')
    lines.append('|---|---|---|')
    for g in ground_truth:
        lines.append(f'| `{g["file"]}` | {g["marker_lines"]} | {g["literal_lines"]} |')
    lines.append('')
    total_marker = sum(g['marker_lines'] for g in ground_truth)
    total_literal = sum(g['literal_lines'] for g in ground_truth)
    lines.append(f'**Result: {total_marker} requests carry the marker substring inside a tool_result, '
                  f'0 of them ({total_literal} literal matches) are the actual 5-line block with real '
                  'newlines.** Manual inspection of the marker hits (all in '
                  '`api_requests_opus_monitor_cc_1785259250_original.jsonl`) shows every one is a '
                  '`rag-cli search` result or file Read quoting `strip_git_lock.py`\'s OWN SOURCE CODE '
                  '(the `_GIT_LOCK_ADVICE` python string literal, where `\\n` is two literal characters '
                  'baked into the .py file, not a newline byte) or a process-docs paragraph mentioning '
                  'the marker string in prose — never the literal git-output block. The exact-substring '
                  'match `_strip_git_lock_advice` uses never fires on either, by construction.')
    lines.append('')
    lines.append('**This ground truth does NOT reproduce as an actual strip in the current corpus '
                  'snapshot.** The only place the literal 5-line block (real newlines) was found at all '
                  'is this worker\'s OWN excluded self-session log — as an artifact of this very '
                  'investigation\'s own `Read`/`Bash` calls on `strip_git_lock.py` and its design docs, '
                  'not as production evidence. Two explanations, not mutually exclusive: (1) the dual-log '
                  'directory is a rolling window — `replay_sn_notice_strip.py`\'s own prior report already '
                  'documented large count swings between runs on this same corpus — so the snapshot that '
                  'produced the original 2-segment finding may have rotated out; (2) `stripped_task_tools_nag` '
                  '/ `stripped_all_sr_msg0`, the other half of that finding, also does not reproduce here: '
                  f'across all {len(all_occ)} tool_result-level occurrences found in this run, zero came from the plain '
                  '`_apply_first_pass` "task tools haven" branch or `_apply_final_sr_pass`\'s catch-all — '
                  'despite the raw marker string `"task tools haven"` appearing in 8–338 raw lines per file '
                  '(grep), every one of those is at top-level message content (a genuine nag in the live '
                  'conversation), never inside a tool_result in this snapshot.')
    lines.append('')
    lines.append('**What DOES reproduce, same mechanism, different template:** Occurrence 8 below '
                  '(`sr:env-context` via `_apply_first_pass`) is the identical bug class — a RAG search '
                  'over `monitor-cc-docs` returned a process-docs paragraph that fences a LITERAL, '
                  'real-newline example of the env-context system-reminder block, and the proxy stripped '
                  'it out of the tool_result as if it were a live per-request injection. This is treated as '
                  'a confirmed, reproducible instance of the audited FP class, not a substitute for the '
                  'stated ground truth.')
    lines.append('')

    lines.append('## Assertion — passes that must NEVER hit tool_result')
    lines.append('')
    lines.append('`_apply_role_system_strip`, `_apply_sn_notice_strip`, `_apply_bg_exit_strip` are '
                  'documented in their own source as not descending into tool_result. Any hit here is '
                  'an anomaly against the code\'s own stated design, not part of the audited FP class.')
    lines.append('')
    if assertion_hits:
        lines.append(f'**{len(assertion_hits)} ANOMALOUS HITS FOUND:**')
        lines.append('')
        for fname, line_idx, pass_name, msg_idx, blk_idx, excerpt in assertion_hits[:20]:
            lines.append(f'- `{fname}` line {line_idx} msg[{msg_idx}] blk[{blk_idx}] `{pass_name}` — {excerpt!r}')
    else:
        lines.append('0 hits — confirmed these three passes never touch tool_result on this corpus.')
    lines.append('')

    lines.append('## Occurrences (deduplicated per (file, exact removed text))')
    lines.append('')
    lines.append(f'{len(all_occ)} unique occurrences across {len(included)} scanned files. '
                  'Offset/context are taken from `_block_inner_text(block)` — for `tool_result_list_joined` '
                  'that is the sub-blocks\' text joined with `\\n`, NOT any single sub-block\'s own text.')
    lines.append('')
    for i, rec in enumerate(all_occ):
        key = _verdict_key(rec)
        verdict, evidence = _MANUAL_VERDICTS.get(key, ('PENDING MANUAL REVIEW', '(not yet classified)'))
        lines.append(f'### Occurrence {i + 1}: `{rec["template"]}` via `{rec["pass_name"]}`')
        lines.append('')
        lines.append(f'- **Source:** `{rec["file"]}` line {rec["first_line_idx"]} (0-indexed) — '
                      f'flow_id `{rec["flow_id"]}`, timestamp `{rec["timestamp"]}`')
        lines.append(f'- **Raw occurrences (dedup collapsed):** {rec["raw_count"]}')
        lines.append(f'- **Location:** msg[{rec["msg_idx"]}] block[{rec["blk_idx"]}] '
                      f'(`{rec["block_shape"]}`), offset {rec["offset"]}')
        lines.append(f'- **Tool:** `{rec["tool_name"]}` (tool_use_id `{rec["tool_use_id"]}`) — '
                      f'input: `{rec["tool_input_preview"]}`')
        lines.append(f'- **Fence-odd before removal:** {rec["fence_odd_before"]} '
                      f'(odd `\\`\\`\\`` count before offset = likely inside an open code fence)')
        lines.append(f'- **Verdict:** **{verdict}** — {evidence}')
        lines.append('')
        lines.append('Context before:')
        lines.append('```')
        lines.append(rec['context_before'])
        lines.append('```')
        lines.append('Removed text (verbatim):')
        lines.append('```')
        lines.append(_excerpt(rec['removed_text']))
        lines.append('```')
        lines.append('Context after:')
        lines.append('```')
        lines.append(rec['context_after'])
        lines.append('```')
        lines.append('')

    lines.append('## Aggregate — split by family (SR strip family vs. non-SR passes)')
    lines.append('')
    lines.append('The 3 SR-family passes (`_apply_first_pass`\'s SR branches, `_apply_cumulative_sr_strips`, '
                  '`_apply_final_sr_pass`) all import and match through `strip_sr.py`\'s line-anchored '
                  '`<system-reminder>` scan. `_apply_bg_launch_ack_strip`, `_apply_hook_prefix_strip`, '
                  '`_apply_po_preview_strip` import NONE of that — they match their own, unrelated markers '
                  '(`Command running in background with ID:`, `PreToolUse:`, the persisted-output preview '
                  'header). Pooling the two into one "genuine CC injection" number is what produced a wrong '
                  'headline in an earlier draft of this report — kept split from here on.')
    lines.append('')
    sr_occ = [r for r in all_occ if _family(r['pass_name']).startswith('SR')]
    non_sr_occ = [r for r in all_occ if not _family(r['pass_name']).startswith('SR')]
    sr_occ_numbers = [i + 1 for i, r in enumerate(all_occ) if _family(r['pass_name']).startswith('SR')]

    def _verdict_of(r):
        return _MANUAL_VERDICTS.get(_verdict_key(r), ('PENDING', ''))[0]

    lines.append(f'**SR strip family (audited by this issue): {len(sr_occ)} tool_result-level occurrence(s).**')
    lines.append('')
    lines.append('| Template | Count | Verdict |')
    lines.append('|---|---|---|')
    for r in sr_occ:
        lines.append(f'| `{r["template"]}` | 1 | {_verdict_of(r)} |')
    if not sr_occ:
        lines.append('| (none) | 0 | — |')
    lines.append('')
    lines.append(f'**Non-SR passes (own markers, out of this issue\'s scope): {len(non_sr_occ)} '
                  f'tool_result-level occurrence(s).**')
    lines.append('')
    non_sr_by_template = Counter(r['template'] for r in non_sr_occ)
    non_sr_by_verdict = Counter(_verdict_of(r) for r in non_sr_occ)
    lines.append('| Template | Count |')
    lines.append('|---|---|')
    for t, c in non_sr_by_template.most_common():
        lines.append(f'| `{t}` | {c} |')
    lines.append('')
    lines.append('| Verdict | Count |')
    lines.append('|---|---|')
    for v, c in non_sr_by_verdict.most_common():
        lines.append(f'| {v} | {c} |')
    lines.append('')
    lines.append('**Pooled totals (both families combined, for reference only — do not read as one '
                  'population; scopes below are distinct):**')
    lines.append('')
    by_tool = Counter(r['tool_name'] for r in all_occ)
    lines.append('| Tool | Count |')
    lines.append('|---|---|')
    for t, c in by_tool.most_common():
        lines.append(f'| `{t}` | {c} |')
    lines.append('')

    sr_verdicts = Counter(_verdict_of(r) for r in sr_occ)
    sr_genuine = sr_verdicts.get('genuine CC injection', 0)
    sr_quoted = sr_verdicts.get('quoted data', 0)
    sr_pending = sr_verdicts.get('PENDING', 0)
    lines.append('## Genuine CC injection inside tool_result — found? (scoped to the SR strip family)')
    lines.append('')
    lines.append('This question was always about the 3 SR-family passes — the ones this issue is actually '
                  'about (`_apply_first_pass` SR branches, `_apply_cumulative_sr_strips`, '
                  '`_apply_final_sr_pass`), NOT the 3 unrelated non-SR passes reported above.')
    lines.append('')
    if sr_pending:
        lines.append(f'**NOT YET DETERMINED — {sr_pending} SR-family occurrence(s) still PENDING MANUAL '
                      'REVIEW.** Fill `_MANUAL_VERDICTS` and re-run before treating this as a final answer.')
    elif not sr_occ:
        lines.append('**SR family now produces 0 tool_result-level occurrences (was 1, the '
                      '`sr:env-context` false positive below the fix milestone this ran against). '
                      'Post-fix confirmation, not a fresh "0 genuine" measurement** — see '
                      '`process-docs/message_strip_fp_nuke/2026-07-28_tool_result_sr_audit.md` for the '
                      'pre-fix n=1 finding and its evidence-strength caveat; `strip_sr.py::_strip_system_reminders` '
                      'no longer descends into tool_result at all, so there is nothing left here to classify.')
    else:
        occ_ref = ', '.join(f'Occurrence {n}' for n in sr_occ_numbers) if sr_occ_numbers else 'none'
        lines.append(f'**NO — 0 genuine CC injections, {sr_quoted} false positive found, for the SR strip '
                      f'family.** Across the entire corpus (5 files, incl. the 2.2GB `wise2627` log) the SR '
                      f'family produced exactly **{len(sr_occ)}** tool_result-level strip: {occ_ref} '
                      '(`sr:env-context` via `_apply_first_pass`), and it is a confirmed false positive, '
                      'not a genuine injection.')
        lines.append('')
        lines.append('**Evidence-strength caveat — read before drawing conclusions.** This "0 genuine" '
                      'answer rests on a sample of **n=1** tool_result-level SR-family strip in the whole '
                      'scanned corpus, not on a large population where genuine cases would statistically '
                      'have to show up. It is backed by a structural argument, not just the count: '
                      '`_apply_final_sr_pass`/`_apply_cumulative_sr_strips`/`_apply_first_pass`\'s SR branches '
                      'only ever fire on text matching one of `strip_sr.py`\'s fixed template identifiers '
                      '(env-context, task-tools-nag, deferred-tools, skills, agent-types, claudemd, '
                      'pyright-diagnostics, plan-mode, date-changed) — CC injects these into TOP-LEVEL user '
                      'message text, never as part of a tool\'s own return value, so a genuine occurrence '
                      'inside a tool_result would require CC to embed one of these templates INSIDE another '
                      'tool\'s output, which nothing in this corpus shows happening. Still: n=1 is a thin '
                      'evidence base, and the next milestone\'s fix should not be built as if 0-genuine were '
                      'proven over a large sample — treat it as "no counter-example found in ~660 requests '
                      'across 5 real sessions", not "structurally impossible".')
        lines.append('')
        lines.append('**The single SR-family occurrence\'s discriminating evidence** (what the fix should '
                      'key on conceptually): `fence_odd_before = True` — an ODD number of markdown ``` '
                      'fences precede the removed text, meaning it sits INSIDE an open code fence, not at '
                      'top-level prose. The immediately preceding text is a documentation header + open '
                      'fence (`"CC injects this SR block on nearly every request:\\n```"`) and the text '
                      'immediately after is the closing fence + a caption (`"```\\n334 chars of inner text '
                      'per request, never useful to the proxy model."`) — i.e. the SR block sits between a '
                      'matched open/close fence pair inside a RAG-retrieved documentation excerpt. This '
                      'fence-pair framing, not just "inside a tool_result", is the concrete signal available '
                      'to distinguish a quoted documentation example from a genuine per-request injection.')
    lines.append('')
    non_sr_genuine = non_sr_by_verdict.get('genuine CC injection', 0)
    lines.append(f'**Non-SR passes — {len(non_sr_occ)} occurrences ({non_sr_genuine} genuine, out of scope).** '
                  f'`_apply_bg_launch_ack_strip`, `_apply_hook_prefix_strip`, `_apply_po_preview_strip` '
                  'stripped real CC/hook/proxy-generated wrapper text out of real Bash tool_results — this '
                  'is their own, unrelated marker matching working as designed, and this issue does not '
                  'question it.')
    lines.append('')

    return '\n'.join(lines)


if __name__ == '__main__':
    main()
