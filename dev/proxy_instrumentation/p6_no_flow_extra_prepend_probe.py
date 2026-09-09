"""
p6_no_flow_extra_prepend_probe.py — the expanded body is the request's payload delta, nothing else.

Replaces `p6_flow_extra_suppress_probe.py` (2026-08-30). That probe verified a PARTIAL suppression
of the out-of-window prepend (total_tokens nuke only) by rendering each entry twice, once with the
suppression disabled. The prepend mechanism was removed entirely hours later, so there is no second
rendering to compare against any more — the invariants below are self-contained instead, which also
means they keep holding as the recorded logs grow.

Drives the REAL read path (`_parse_forwarded_log` -> `accumulate_dual_log` -> pane-style entry
attach -> `render_messages`) over recorded sessions and asserts:

  1. No entry's body contains a `[N]` message header BELOW that entry's own delta-window start
     (prev_msg_count for the new-messages branch, diff_start for the modified branch). This is the
     property the removal bought: body == payload delta.
  2. `_render_flow_extra_messages` and `_own_msgs` no longer exist in `render_messages`, and no
     entry carries a `_strip_msgs_sub_lookup` / `_inject_msgs_sub_lookup` attachment — a
     reintroduction guard, since a partial revert would otherwise pass check 1 silently.
  3. Every entry whose out-of-window touch is SUBSTANTIAL still badges — those badge words are now
     the ONLY in-pane trace of such a strip. Substantiality is read off the raw dual-log lines via
     `parser._msg_delta_entry_is_substantial`, because a touch that is only the per-request
     total_tokens nuke deliberately badges nothing (the 2026-08-29 divergence) and must not be
     demanded here.
  4. The in-window path still renders spans: at least one entry shows an olive or green span, so a
     regression that killed span rendering outright cannot pass as "no prepend".
  5. The write-side LAG CORRECTION holds (2026-08-30): every coordinate the parser attributes back
     to the flow that actually stripped it carries the total_tokens marker text (never a
     mid-conversation overwrite such as the task-tools nag, which would be neighbour bleed), and
     every such coordinate falling inside its flow's delta window really renders an olive span and
     a green ".". Without the correction those messages render as a bare "." — the defect this
     check guards.

It also REPORTS (never asserts) how many entries have an out-of-window touched index whose stripped
original is therefore invisible in the pane — the accepted cost of the removal, recoverable only
from the dual-log `_stripped` stream (e.g. via the duallog CLI).

Usage (from project root):
    ./venv/bin/python dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py
    ./venv/bin/python dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py <stem> [<stem> ...]
"""

# INFRASTRUCTURE
import re
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

# Recorded dual-log sessions are untracked data living in the main checkout, never duplicated into
# worktrees — code under test is imported from WORKTREE_ROOT above.
MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

DEFAULT_STEMS = (
    'api_requests_opus_monitor_cc_1788091735',
    'api_requests_opus_gh_cli_1787995963',
)

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'no_flow_extra_prepend_report.md'

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
_MSG_HEADER_RE = re.compile(r'^    (?:removed:\s*)?\[\s*(\d+)\] ')
DIM_YELLOW_BG = '\033[48;2;94;81;47m'
DIM_GREEN_BG = '\033[48;2;38;74;46m'
_ACC_KEYS = ('system', 'tools', 'messages', 'fields', '_has_content_by_flow_id', '_msg_idx_by_flow_id')

# FUNCTIONS


# Load one recorded session the way pane.py assembles it, messages retained for every entry
def _load_session(stem: str) -> list:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log, _infer_model_family
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log
    entries, _ = _parse_forwarded_log(LOG_DIR / f'{stem}_forwarded.jsonl', 0, {}, keep_last=None)
    acc_s: dict = {}
    acc_i: dict = {}
    accumulate_dual_log(LOG_DIR / f'{stem}_stripped.jsonl', 0, acc_s)
    accumulate_dual_log(LOG_DIR / f'{stem}_injected.jsonl', 0, acc_i)
    for entry in entries:
        family = _infer_model_family(entry.get('model', ''))
        fam_s = acc_s.setdefault(family, {k: {} for k in _ACC_KEYS})
        fam_i = acc_i.setdefault(family, {k: {} for k in _ACC_KEYS})
        entry['_stripped_spans'] = fam_s
        entry['_injected_spans'] = fam_i
        entry['_strip_fns_lookup'] = fam_s.setdefault('_has_content_by_flow_id', {})
        entry['_inject_fns_lookup'] = fam_i.setdefault('_has_content_by_flow_id', {})
        entry['_strip_msgs_lookup'] = fam_s.setdefault('_msg_idx_by_flow_id', {})
        entry['_inject_msgs_lookup'] = fam_i.setdefault('_msg_idx_by_flow_id', {})
        entry['_lag_msgs_lookup'] = fam_s.setdefault('_lag_msg_idx_by_flow_id', {})
    return entries


# The first msg index this entry's delta window covers — mirrors render_messages' own branch
# choice, recomputed here rather than imported so the probe cannot drift into agreeing by
# construction with the code it checks
def _delta_window_start(entry: dict, prev_entry) -> int:
    messages = entry.get('messages', []) or []
    prev_msg_count = prev_entry.get('message_count', 0) if prev_entry is not None else 0
    if prev_msg_count < len(messages):
        return prev_msg_count
    prev_messages = prev_entry.get('messages', []) if prev_entry is not None else []
    diff_start = len(messages)
    for j in range(1, min(len(messages), len(prev_messages)) + 1):
        curr_msg = messages[-j]
        prev_msg = prev_messages[-j]
        if curr_msg.get('chars', 0) != prev_msg.get('chars', 0) or curr_msg.get('type', '') != prev_msg.get('type', ''):
            diff_start = len(messages) - j
        else:
            break
    return diff_start


# Msg indices appearing as top-level headers in a rendered body
def _header_indices(body: str) -> list:
    return [int(m.group(1)) for m in
            (_MSG_HEADER_RE.match(line) for line in _ANSI_RE.sub('', body).splitlines()) if m]


# Render every entry; returns {entry_idx: (body, window_start, out_of_window_touches)}
def _render_all(entries: list) -> dict:
    from src.proxy_display.render_messages import render_messages
    from src.proxy_display.render_turn import _resolve_prev_same_family
    out: dict = {}
    for idx, entry in enumerate(entries):
        if entry.get('messages') is None:
            continue
        prev = _resolve_prev_same_family(entries, idx)
        lines, _keys = render_messages(idx, entry, prev, entries, {}, 200)
        start = _delta_window_start(entry, prev)
        fid = entry.get('flow_id', '')
        touched = (entry.get('_strip_msgs_lookup', {}).get(fid, set())
                   | entry.get('_inject_msgs_lookup', {}).get(fid, set()))
        outside = sorted(int(m) for m in touched
                         if int(m) < start and int(m) < len(entry.get('messages', [])))
        out[idx] = ('\n'.join(lines), start, outside)
    return out


# {(flow_id, msg_idx): True} for every delta entry the parser calls substantial, read straight off
# the raw dual-log lines — the same verdict the badge rests on
def _substantial_touches(stem: str) -> dict:
    import json
    from src.proxy_display.proxy_badge import _msg_delta_entry_is_substantial
    verdicts: dict = {}
    for side, is_injected in (('stripped', False), ('injected', True)):
        for raw in (LOG_DIR / f'{stem}_{side}.jsonl').read_text(encoding='utf-8').splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                line = json.loads(raw)
            except json.JSONDecodeError:
                continue
            fid = line.get('flow_id', '')
            for midx, blks in (line.get('messages_delta') or {}).items():
                key = (fid, int(midx))
                verdicts[key] = verdicts.get(key, False) or _msg_delta_entry_is_substantial(blks, is_injected)
    return verdicts


# Check 5: the lag correction is marker-only, and the coordinates it fixes really render spans.
# Returns (coords_with_wrong_text, coords_in_window_without_spans, total_corrected).
def _check_lag_correction(entries: list, rendered: dict) -> tuple:
    marker = re.compile(r'^<total_tokens>\d+ tokens left</total_tokens>$')
    accs = {}
    for entry in entries:
        lag = entry.get('_lag_msgs_lookup')
        if lag is not None and id(lag) not in accs:
            accs[id(lag)] = (lag, entry['_stripped_spans']['messages'])
    bad_text = []
    total = 0
    for lag, spans in accs.values():
        for fid, idxs in lag.items():
            for i in idxs:
                total += 1
                texts = [t for b in spans.get(i, {}).values() if isinstance(b, list)
                         for t in b if isinstance(t, str)]
                if not (len(texts) == 1 and marker.match(texts[0].strip())):
                    bad_text.append((fid[:8], i, str(texts)[:50]))
    unrendered = []
    for idx, (body, start, _outside) in rendered.items():
        fid = entries[idx].get('flow_id', '')
        for i in entries[idx].get('_lag_msgs_lookup', {}).get(fid, set()):
            if int(i) < start:
                continue  # outside this entry's delta window — nothing is drawn there at all
            if DIM_YELLOW_BG not in body or DIM_GREEN_BG not in body:
                unrendered.append((idx, i))
    return bad_text, unrendered, total


# Checks 2's source-level half: the removed symbols must not come back
def _removed_symbols_absent() -> tuple:
    from src.proxy_display import render_messages as rm
    gone = [name for name in ('_render_flow_extra_messages', '_own_msgs') if hasattr(rm, name)]
    src = (WORKTREE_ROOT / 'src' / 'proxy_display' / 'parser.py').read_text()
    acc_key = '_msg_idx_sub_by_flow_id' in src
    return gone, acc_key


# One session: render, assert the four invariants, return (rows, stats)
def _check_session(stem: str) -> tuple:
    from src.proxy_display.proxy_badge import badge_flags
    entries = _load_session(stem)
    rendered = _render_all(entries)

    below = []
    for idx, (body, start, _outside) in rendered.items():
        low = [h for h in _header_indices(body) if h < start]
        if low:
            below.append((idx, start, low[:4]))

    gone, acc_key = _removed_symbols_absent()
    sub_attached = [idx for idx, e in enumerate(entries)
                    if '_strip_msgs_sub_lookup' in e or '_inject_msgs_sub_lookup' in e]

    badges = {idx: badge_flags(entries[idx]) for idx in rendered}
    verdicts = _substantial_touches(stem)
    with_outside = [idx for idx, (_b, _s, outside) in rendered.items() if outside]
    with_real_outside = [
        idx for idx in with_outside
        if any(verdicts.get((entries[idx].get('flow_id', ''), m), False)
               for m in rendered[idx][2])
    ]
    silent = [idx for idx in with_real_outside if not any(badges[idx])]

    spans_seen = sum(1 for body, _s, _o in rendered.values()
                     if DIM_YELLOW_BG in body or DIM_GREEN_BG in body)

    lag_bad_text, lag_unrendered, lag_total = _check_lag_correction(entries, rendered)

    rows = [
        ('no_msg_below_delta_window', not below,
         f'{len(rendered)} entries rendered; bodies starting below their own delta window: '
         f'{len(below)} {below[:3]}'),
        ('removed_symbols_stay_removed', not gone and not acc_key and not sub_attached,
         f'render_messages still exporting {gone or "none"}; parser mentions '
         f'_msg_idx_sub_by_flow_id: {acc_key}; entries carrying a sub-lookup: {len(sub_attached)}'),
        ('substantial_out_of_window_strips_still_badge', not silent,
         f'{len(with_outside)} entries have an out-of-window touched index, {len(with_real_outside)} '
         f'of them SUBSTANTIAL; of those {len(silent)} show NO badge word (want 0) {silent[:3]}'),
        ('in_window_spans_still_render', spans_seen > 0,
         f'{spans_seen} of {len(rendered)} entries render an olive/green span in-window'),
        ('lag_correction_sound_and_effective', not lag_bad_text and not lag_unrendered,
         f'{lag_total} coordinates re-attributed to the flow that stripped them; '
         f'{len(lag_bad_text)} carry non-marker text (want 0) {lag_bad_text[:2]}; '
         f'{len(lag_unrendered)} sit in-window without olive+green (want 0) {lag_unrendered[:2]}'),
    ]
    stats = {
        'entries_rendered': len(rendered),
        'entries_with_out_of_window_touch': len(with_outside),
        'entries_whose_out_of_window_touch_is_substantial': len(with_real_outside),
        'out_of_window_indices_now_invisible': sum(len(o) for _b, _s, o in rendered.values()),
        'entries_showing_in_window_spans': spans_seen,
        'lag_corrected_coordinates': lag_total,
    }
    return rows, stats


# ORCHESTRATOR
def main() -> None:
    stems = sys.argv[1:] or list(DEFAULT_STEMS)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# No-prepend probe — the expanded body is the request payload delta only', '']
    lines.append('The out-of-window flow-extra prepend was removed on 2026-08-30. These invariants')
    lines.append('are self-contained: there is no pre-change rendering left to diff against, and')
    lines.append('counts are reported rather than asserted so log growth cannot break them.')
    lines.append('')
    all_pass = True
    for stem in stems:
        if not (LOG_DIR / f'{stem}_forwarded.jsonl').exists():
            print(f'SKIP {stem} — no recorded forwarded log')
            lines += [f'## `{stem}` — SKIPPED (log not on disk)', '']
            continue
        rows, stats = _check_session(stem)
        lines += [f'## `{stem}`', '', '| metric | value |', '|---|---|']
        lines += [f'| {k} | {v} |' for k, v in stats.items()]
        lines += ['', '| check | pass | detail |', '|---|---|---|']
        print(f'\n== {stem}  ' + '  '.join(f'{k}={v}' for k, v in stats.items()))
        for label, ok, detail in rows:
            all_pass = all_pass and ok
            lines.append(f'| {label} | {"PASS" if ok else "FAIL"} | {detail} |')
            print(('PASS' if ok else 'FAIL'), label, '-', detail)
        lines.append('')
    lines.append(f'## Overall: {"ALL PASS" if all_pass else "FAILURES PRESENT"}')
    REPORT_PATH.write_text('\n'.join(lines) + '\n')
    print(f'\nReport written: {REPORT_PATH}')
    print('ALL PASS' if all_pass else 'FAILURES PRESENT')
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
