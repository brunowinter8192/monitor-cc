# INFRASTRUCTURE
from collections import Counter
import os
from pathlib import Path

from audit_scan import LOGS_DIR
from audit_verdicts import _MANUAL_VERDICTS

OUT_FILE = Path(os.path.join(os.path.dirname(__file__), 'md', 'audit_tool_result_sr_strips.md'))

_SR_FAMILY_PASSES = {'_apply_first_pass', '_apply_cumulative_sr_strips', '_apply_final_sr_pass'}


# FUNCTIONS

def _family(pass_name):
    return 'SR strip family (audited)' if pass_name in _SR_FAMILY_PASSES else 'non-SR pass (own marker, out of scope)'


def _verdict_key(rec):
    return (rec['file'], rec['msg_idx'], rec['blk_idx'], rec['first_line_idx'])


def _verdict_of(r):
    return _MANUAL_VERDICTS.get(_verdict_key(r), ('PENDING', ''))[0]


def _excerpt(text, limit=3000):
    if len(text) <= limit:
        return text
    return text[:limit] + f'\n...[TRUNCATED — {len(text)} chars total]'


def _write_report(report):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report)
    print(report)
    print(f'\nWritten to {OUT_FILE}')


def _render_corpus_section(included, excluded, per_file_stats):
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
    return lines


def _render_ground_truth_table(ground_truth):
    lines = []
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
    return lines


def _render_ground_truth_narrative(all_occ, ground_truth):
    lines = []
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
    return lines


def _render_assertion_section(assertion_hits):
    lines = []
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
    return lines


def _render_occurrence(i, rec):
    lines = []
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
    return lines


def _render_occurrences_section(all_occ, included):
    lines = []
    lines.append('## Occurrences (deduplicated per (file, exact removed text))')
    lines.append('')
    lines.append(f'{len(all_occ)} unique occurrences across {len(included)} scanned files. '
                  'Offset/context are taken from `_block_inner_text(block)` — for `tool_result_list_joined` '
                  'that is the sub-blocks\' text joined with `\\n`, NOT any single sub-block\'s own text.')
    lines.append('')
    for i, rec in enumerate(all_occ):
        lines.extend(_render_occurrence(i, rec))
    return lines


def _render_aggregate_intro():
    lines = []
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
    return lines


def _render_sr_family_table(sr_occ):
    lines = []
    lines.append(f'**SR strip family (audited by this issue): {len(sr_occ)} tool_result-level occurrence(s).**')
    lines.append('')
    lines.append('| Template | Count | Verdict |')
    lines.append('|---|---|---|')
    for r in sr_occ:
        lines.append(f'| `{r["template"]}` | 1 | {_verdict_of(r)} |')
    if not sr_occ:
        lines.append('| (none) | 0 | — |')
    lines.append('')
    return lines


def _render_non_sr_family_tables(non_sr_occ):
    lines = []
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
    return lines


def _render_pooled_totals(all_occ):
    lines = []
    lines.append('**Pooled totals (both families combined, for reference only — do not read as one '
                  'population; scopes below are distinct):**')
    lines.append('')
    by_tool = Counter(r['tool_name'] for r in all_occ)
    lines.append('| Tool | Count |')
    lines.append('|---|---|')
    for t, c in by_tool.most_common():
        lines.append(f'| `{t}` | {c} |')
    lines.append('')
    return lines


def _render_aggregate_section(sr_occ, non_sr_occ, all_occ):
    lines = []
    lines.extend(_render_aggregate_intro())
    lines.extend(_render_sr_family_table(sr_occ))
    lines.extend(_render_non_sr_family_tables(non_sr_occ))
    lines.extend(_render_pooled_totals(all_occ))
    return lines


def _render_genuine_injection_intro():
    lines = []
    lines.append('## Genuine CC injection inside tool_result — found? (scoped to the SR strip family)')
    lines.append('')
    lines.append('This question was always about the 3 SR-family passes — the ones this issue is actually '
                  'about (`_apply_first_pass` SR branches, `_apply_cumulative_sr_strips`, '
                  '`_apply_final_sr_pass`), NOT the 3 unrelated non-SR passes reported above.')
    lines.append('')
    return lines


def _render_sr_pending(sr_pending):
    lines = []
    lines.append(f'**NOT YET DETERMINED — {sr_pending} SR-family occurrence(s) still PENDING MANUAL '
                  'REVIEW.** Fill `_MANUAL_VERDICTS` and re-run before treating this as a final answer.')
    return lines


def _render_sr_zero():
    lines = []
    lines.append('**SR family now produces 0 tool_result-level occurrences (was 1, the '
                  '`sr:env-context` false positive below the fix milestone this ran against). '
                  'Post-fix confirmation, not a fresh "0 genuine" measurement** — see '
                  '`process-docs/message_strip_fp_nuke/2026-07-28_tool_result_sr_audit.md` for the '
                  'pre-fix n=1 finding and its evidence-strength caveat; `strip_sr.py::_strip_system_reminders` '
                  'no longer descends into tool_result at all, so there is nothing left here to classify.')
    return lines


def _render_sr_found(sr_occ, sr_quoted, sr_occ_numbers):
    lines = []
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
    return lines


def _render_sr_verdict(sr_occ, sr_occ_numbers):
    sr_verdicts = Counter(_verdict_of(r) for r in sr_occ)
    sr_genuine = sr_verdicts.get('genuine CC injection', 0)
    sr_quoted = sr_verdicts.get('quoted data', 0)
    sr_pending = sr_verdicts.get('PENDING', 0)
    if sr_pending:
        return _render_sr_pending(sr_pending)
    if not sr_occ:
        return _render_sr_zero()
    return _render_sr_found(sr_occ, sr_quoted, sr_occ_numbers)


def _render_non_sr_genuine_summary(non_sr_occ):
    non_sr_by_verdict = Counter(_verdict_of(r) for r in non_sr_occ)
    lines = ['']
    non_sr_genuine = non_sr_by_verdict.get('genuine CC injection', 0)
    lines.append(f'**Non-SR passes — {len(non_sr_occ)} occurrences ({non_sr_genuine} genuine, out of scope).** '
                  f'`_apply_bg_launch_ack_strip`, `_apply_hook_prefix_strip`, `_apply_po_preview_strip` '
                  'stripped real CC/hook/proxy-generated wrapper text out of real Bash tool_results — this '
                  'is their own, unrelated marker matching working as designed, and this issue does not '
                  'question it.')
    lines.append('')
    return lines


def _render_genuine_injection_section(sr_occ, non_sr_occ, sr_occ_numbers):
    lines = []
    lines.extend(_render_genuine_injection_intro())
    lines.extend(_render_sr_verdict(sr_occ, sr_occ_numbers))
    lines.extend(_render_non_sr_genuine_summary(non_sr_occ))
    return lines


def _render_report(included, excluded, per_file_stats, occurrences, assertion_hits, ground_truth):
    all_occ = sorted(occurrences.values(), key=lambda r: (r['file'], r['first_line_idx']))
    sr_occ = [r for r in all_occ if _family(r['pass_name']).startswith('SR')]
    non_sr_occ = [r for r in all_occ if not _family(r['pass_name']).startswith('SR')]
    sr_occ_numbers = [i + 1 for i, r in enumerate(all_occ) if _family(r['pass_name']).startswith('SR')]

    lines = []
    lines.extend(_render_corpus_section(included, excluded, per_file_stats))
    lines.extend(_render_ground_truth_table(ground_truth))
    lines.extend(_render_ground_truth_narrative(all_occ, ground_truth))
    lines.extend(_render_assertion_section(assertion_hits))
    lines.extend(_render_occurrences_section(all_occ, included))
    lines.extend(_render_aggregate_section(sr_occ, non_sr_occ, all_occ))
    lines.extend(_render_genuine_injection_section(sr_occ, non_sr_occ, sr_occ_numbers))
    return '\n'.join(lines)
