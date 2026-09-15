# INFRASTRUCTURE
from collections import defaultdict
from datetime import datetime, timezone

from blast_radius_engine import PASS_CLASS, FIRST_PASS_BRANCH_CLASS
from blast_radius_analysis import _trimmed, _ratio, _dist, _render_comparison


# FUNCTIONS

def _report_corpus_section(ts, total_requests, records, corpus_files, excluded_files):
    lines = []
    lines.append('# D2 — full-replacement blast-radius measurement for `_extract_block_op`')
    lines.append('')
    lines.append(f'Generated: {ts}')
    lines.append('')
    lines.append('## Corpus')
    lines.append('')
    lines.append('| File | Included | Notes |')
    lines.append('|---|---|---|')
    for fname in corpus_files:
        lines.append(f'| `{fname}` | yes | |')
    for fname, reason in excluded_files.items():
        lines.append(f'| `{fname}` | **excluded** | {reason} |')
    lines.append('')
    lines.append(f'Total requests scanned (deduped, new-messages-only pass): {total_requests}')
    lines.append(f'Total ops captured across all 17 call sites: {len(records)}')
    lines.append('')
    return lines


def _report_classification_table():
    lines = []
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
    return lines


def _report_per_pass_counts(records):
    by_site = defaultdict(list)
    for r in records:
        by_site[r['site']].append(r)

    lines = []
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
    return lines


def _report_blast_radius_section(full_recs):
    lines = []
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
    return lines


def _report_edge_case_section(full_recs):
    lines = []
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
    return lines, dot_absorbed


def _report_ratio_section(full_recs, partial_recs, struct_recs):
    lines = []
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
    return lines


def _report_structural_section(struct_recs):
    lines = []
    lines.append('## Structural (index-shift) sites — `_dedup_wakeup_blocks:list`')
    lines.append('')
    lines.append(f'Ops observed: **{len(struct_recs)}**.')
    if struct_recs:
        lines.append('(present in corpus — see per-pass table above for count; not folded into FULL/PARTIAL)')
    else:
        lines.append('0 occurrences in this corpus — reported plainly, not manufactured.')
    lines.append('')
    return lines


def _pick(predicate, pool):
    for r in pool:
        if predicate(r):
            return r
    return None


def _pick_examples(full_recs, partial_recs, dot_absorbed):
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
    return examples


def _render_example_lines(label, rec):
    lines = []
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
    return lines


def _report_examples_section(full_recs, partial_recs, dot_absorbed):
    lines = []
    lines.append('## Concrete rendered before/after — real `compose_block` + `_render_span_content`')
    lines.append('')
    examples = _pick_examples(full_recs, partial_recs, dot_absorbed)
    for label, rec in examples:
        lines.extend(_render_example_lines(label, rec))
    return lines


# Build the markdown report
def _build_report(records, total_requests, corpus_files, excluded_files):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines.extend(_report_corpus_section(ts, total_requests, records, corpus_files, excluded_files))
    lines.extend(_report_classification_table())
    lines.extend(_report_per_pass_counts(records))

    full_recs = [r for r in records if r['class'] == 'FULL' and r['bt']]
    partial_recs = [r for r in records if r['class'] == 'PARTIAL' and r['bt']]
    struct_recs = [r for r in records if r['class'] == 'STRUCTURAL' and r['bt']]

    lines.extend(_report_blast_radius_section(full_recs))
    edge_case_lines, dot_absorbed = _report_edge_case_section(full_recs)
    lines.extend(edge_case_lines)
    lines.extend(_report_ratio_section(full_recs, partial_recs, struct_recs))
    lines.extend(_report_structural_section(struct_recs))
    lines.extend(_report_examples_section(full_recs, partial_recs, dot_absorbed))

    return '\n'.join(lines)
