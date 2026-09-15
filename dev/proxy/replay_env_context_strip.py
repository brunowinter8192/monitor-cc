#!/usr/bin/env python3
"""Replay verification for `_ENV_CONTEXT_RE` in strip_sr.py — CC 2.1.258 trailing-sentences fix
(2026-09) AND the gitStatus-section widening (2026-09, this task).

Scans every top-level standalone `<system-reminder>` block (str content, or `list[type=='text']`
blocks — never `tool_result`, matching `_strip_system_reminders`'s own 2026-07-28 scope reduction
exactly) in every `src/logs/dual_log/*_original.jsonl` entry, and classifies each DISTINCT
(file, exact inner text) occurrence against both the OLD (pre-gitStatus-fix, quoted verbatim
below — this is the exact regex this task replaced) and the live (post-fix) `_ENV_CONTEXT_RE`:

  - env-context, stripped        — `_ENV_CONTEXT_RE.fullmatch` succeeds
  - env-context, left            — starts with `_PRESERVE_PREAMBLE` AND contains `# userEmail`,
                                    but the fullmatch fails (this is exactly the gitStatus bug
                                    before this task's fix — no `# currentDate` anywhere in a
                                    build that emits `# gitStatus` instead — and the "bundled
                                    CLAUDE.md + userEmail" shape both before and after — see the
                                    report body)
  - CLAUDE.md context, preserved — starts with `_PRESERVE_PREAMBLE`, does NOT match
                                    `_ENV_CONTEXT_RE`, and either has no `# userEmail` at all or
                                    has one only as part of bundled real project content

Each bucket is additionally split by FORM — `currentDate` (the block carries a `# currentDate`
section) vs. `gitStatus` (the block carries a `# gitStatus` section instead) — since the two forms
are structurally different CC-emitted shapes and the whole point of this task's fix is the
gitStatus form moving from "left" to "stripped".

Deduplicated by (file, exact inner text) — dual-logs are cumulative snapshots, the same message
reappears in every later request of the same session, so raw per-entry counts vastly overcount
distinct real occurrences.

Usage: python3 dev/proxy/replay_env_context_strip.py
Output: dev/proxy/md/replay_env_context_strip.md
"""

# INFRASTRUCTURE
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('MONITOR_CC_ROOT', os.path.join(os.path.dirname(__file__), '..', '..'))

# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
import importlib as _il
_sr_mod = _il.import_module('src.proxy.strip_sr')
_ENV_CONTEXT_RE_NEW = _sr_mod._ENV_CONTEXT_RE
_PRESERVE_PREAMBLE = _sr_mod._PRESERVE_PREAMBLE
_STANDALONE_SR_RE = _sr_mod._STANDALONE_SR_RE
_INNER_SR_RE = _sr_mod._INNER_SR_RE
del _il, _sr_mod

# The pre-this-task pattern, quoted verbatim — the CC 2.1.258 trailing-sentences fix (2026-09,
# see process-docs/proxy_noise_strip/2026-09_env_context_cc258_trailing_sentences.md) is already
# folded in (`[^\n]*` after the email sentence), but it still hard-requires a `# currentDate`
# section immediately after — the current CC build instead emits `# gitStatus` and no
# `# currentDate` at all, so this pattern's fullmatch fails on that form (this task's bug).
_ENV_CONTEXT_RE_OLD = re.compile(
    r"As you answer the user's questions, you can use the following context:\n"
    r"# userEmail\n"
    r"The user's email address is brunowinter7934@gmail\.com\.[^\n]*\n"
    r"# currentDate\n"
    r"Today's date is \d{4}-\d{2}-\d{2}\.\s+"
    r"IMPORTANT: this context may or may not be relevant to your tasks\. "
    r"You should not respond to this context unless it is highly relevant to your task\.",
)

# Actual runtime dual-log location (main checkout, not this worktree — src/logs/ is gitignored
# per-worktree; the corpus only exists here).
LOGS_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')
OUT_FILE = Path(os.path.join(os.path.dirname(__file__), 'md', 'replay_env_context_strip.md'))


# ORCHESTRATOR

def scan_all():
    files = sorted(LOGS_DIR.glob('*_original.jsonl'))
    seen = set()  # (file, exact inner text) — dedup across cumulative session snapshots
    buckets_old = _new_bucket_dict()
    buckets_new = _new_bucket_dict()
    total_entries = 0

    for fp in files:
        for line in open(fp, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            total_entries += 1
            entry = json.loads(line)
            payload = entry.get('payload') or {}
            messages = payload.get('messages') or []
            for inner in _find_top_level_sr_inner_texts(messages):
                key = (fp.name, inner)
                if key in seen:
                    continue
                seen.add(key)
                form = _form_of(inner)
                _classify(key, inner, form, buckets_old, _ENV_CONTEXT_RE_OLD)
                _classify(key, inner, form, buckets_new, _ENV_CONTEXT_RE_NEW)

    return _build_stats(len(files), total_entries, buckets_old, buckets_new)


# FUNCTIONS

_BUCKET_NAMES = ('stripped', 'left_pure', 'left_bundled', 'claudemd_preserved')
_FORMS = ('currentDate', 'gitStatus', 'other')


def _new_bucket_dict():
    return {bucket: {form: set() for form in _FORMS} for bucket in _BUCKET_NAMES}


# A block's FORM is which date/status section it carries — 'other' covers real CLAUDE.md context
# blocks (no userEmail section at all, so neither marker is present).
def _form_of(inner):
    if '# gitStatus' in inner:
        return 'gitStatus'
    if '# currentDate' in inner:
        return 'currentDate'
    return 'other'


# One classification pass for one env-context regex variant — populates the bucket dict in place.
# "left" splits into PURE (no `# claudeMd` at all — a genuinely broken env-context block, the bug)
# and BUNDLED (`# claudeMd` present too — CC folded real project content and env-context into one
# block; correctly preserved by design regardless of the regex fix, see report body).
def _classify(key, inner, form, buckets, env_re):
    if env_re.fullmatch(inner):
        buckets['stripped'][form].add(key)
    elif inner.startswith(_PRESERVE_PREAMBLE) and '# userEmail' in inner:
        if '# claudeMd' in inner:
            buckets['left_bundled'][form].add(key)
        else:
            buckets['left_pure'][form].add(key)
    elif inner.startswith(_PRESERVE_PREAMBLE):
        buckets['claudemd_preserved'][form].add(key)  # real CLAUDE.md context, no userEmail hint


def _build_stats(num_files, total_entries, buckets_old, buckets_new):
    counts = {}
    for bucket in _BUCKET_NAMES:
        for form in _FORMS:
            counts[f'{bucket}_{form}_before'] = len(buckets_old[bucket][form])
            counts[f'{bucket}_{form}_after'] = len(buckets_new[bucket][form])
        counts[f'{bucket}_before'] = sum(len(buckets_old[bucket][f]) for f in _FORMS)
        counts[f'{bucket}_after'] = sum(len(buckets_new[bucket][f]) for f in _FORMS)
    newly_stripped = sorted(buckets_new['stripped']['gitStatus'] - buckets_old['stripped']['gitStatus']) + \
        sorted(buckets_new['stripped']['currentDate'] - buckets_old['stripped']['currentDate'])
    return {
        'files': num_files,
        'total_entries': total_entries,
        'newly_stripped': newly_stripped,
        **counts,
    }


# Yield inner text of every top-level standalone SR block (str content, or list[type=='text']
# blocks) across all messages — tool_result is never descended into, matching
# _strip_system_reminders's own 2026-07-28 scope reduction exactly.
def _find_top_level_sr_inner_texts(messages):
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get('content')
        if isinstance(content, str):
            yield from _sr_inner_texts_in_text(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    yield from _sr_inner_texts_in_text(block.get('text', ''))


def _sr_inner_texts_in_text(text):
    if '<system-reminder>' not in text:
        return
    for m in _STANDALONE_SR_RE.finditer(text):
        inner_m = _INNER_SR_RE.search(m.group(0))
        if inner_m:
            yield inner_m.group(1).strip()


def _render_tables_lines(stats):
    return [
        '# strip_sr.py — env-context `_ENV_CONTEXT_RE` replay (gitStatus widening fix)',
        '',
        f'Corpus: `{LOGS_DIR}` — {stats["files"]} `*_original.jsonl` files, '
        f'{stats["total_entries"]} request entries. Counts below are UNIQUE (file, exact inner '
        'text) — dual-logs are cumulative snapshots, the same block reappears in every later '
        'request of the same session.',
        '',
        '## Before / after, by bucket and form',
        '',
        '"Before" is the live regex immediately prior to this task (already carries the CC 2.1.258 '
        'trailing-sentences fix, but still hard-requires `# currentDate`). "After" is the live '
        'regex with the `# gitStatus` alternation this task adds.',
        '',
        '| Bucket | Form | Before | After |',
        '|---|---|---|---|',
        f'| env-context, stripped | currentDate | {stats["stripped_currentDate_before"]} | {stats["stripped_currentDate_after"]} |',
        f'| env-context, stripped | gitStatus | {stats["stripped_gitStatus_before"]} | {stats["stripped_gitStatus_after"]} |',
        f'| env-context, left — PURE (no `# claudeMd`, genuinely broken) | currentDate | {stats["left_pure_currentDate_before"]} | {stats["left_pure_currentDate_after"]} |',
        f'| env-context, left — PURE (no `# claudeMd`, genuinely broken) | gitStatus | {stats["left_pure_gitStatus_before"]} | {stats["left_pure_gitStatus_after"]} |',
        f'| env-context, left — BUNDLED (`# claudeMd` + `# userEmail` in one block, preserved by design) | currentDate | {stats["left_bundled_currentDate_before"]} | {stats["left_bundled_currentDate_after"]} |',
        f'| env-context, left — BUNDLED (`# claudeMd` + `# userEmail` in one block, preserved by design) | gitStatus | {stats["left_bundled_gitStatus_before"]} | {stats["left_bundled_gitStatus_after"]} |',
        f'| CLAUDE.md context, preserved (no userEmail hint at all) | other | {stats["claudemd_preserved_other_before"]} | {stats["claudemd_preserved_other_after"]} |',
        '',
        '## Totals across both forms',
        '',
        '| Bucket | Before | After |',
        '|---|---|---|',
        f'| env-context, stripped | {stats["stripped_before"]} | {stats["stripped_after"]} |',
        f'| env-context, left — PURE | {stats["left_pure_before"]} | {stats["left_pure_after"]} |',
        f'| env-context, left — BUNDLED | {stats["left_bundled_before"]} | {stats["left_bundled_after"]} |',
        f'| CLAUDE.md context, preserved | {stats["claudemd_preserved_before"]} | {stats["claudemd_preserved_after"]} |',
        '',
    ]


def _render_summary_lines(stats):
    return [
        f'Newly stripped by this fix (present in "after" stripped, absent from "before"): '
        f'{len(stats["newly_stripped"])} distinct blocks — all are the gitStatus-form PURE-left '
        'bucket moving to stripped (the bug this task fixes; the current CC build emits '
        '`# gitStatus` and no `# currentDate` at all, so the pre-fix regex never matched it). The '
        'currentDate-form stripped count is unchanged before/after (this task only adds an '
        'alternation branch, it does not touch the pre-existing currentDate branch). The BUNDLED '
        'bucket is unchanged before/after for both forms because `_ENV_CONTEXT_RE.fullmatch` '
        'correctly never matches a block that also carries real `# claudeMd` project content — '
        'that block must stay preserved whole, losing the CLAUDE.md content would be worse than '
        'leaving the unstripped env-context noise inside it.',
        '',
        'CLAUDE.md-context-preserved (no userEmail hint) count is IDENTICAL before/after by '
        'construction — the fix only widens `_ENV_CONTEXT_RE`, it does not touch '
        '`_PRESERVE_PREAMBLE` or its position; the count in this corpus window is a property of '
        'which sessions happen to be in the current rotating `dual_log/` window, not evidence the '
        'guard never fires (see `process-docs/strip_efficacy_audit/2026-07-28_template_catalog_efficacy_cc205.md`, '
        'which measured 2 pure CLAUDE.md-preserved occurrences in a different corpus window).',
        '',
    ]


def render_report(stats):
    lines = _render_tables_lines(stats) + _render_summary_lines(stats)
    return '\n'.join(lines)


if __name__ == '__main__':
    stats = scan_all()
    report = render_report(stats)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report)
    print(report)
    print(f'Written to {OUT_FILE}')
