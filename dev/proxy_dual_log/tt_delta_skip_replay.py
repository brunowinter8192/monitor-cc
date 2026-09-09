"""
tt_delta_skip_replay.py — before/after replay proving the total_tokens delta-skip.

Replays a recorded _original.jsonl through the REAL production pass pipeline
(`apply_modification_rules`, which is what produces `all_ops` in `addon.py`), then feeds
(orig_payload, fwd_payload, all_ops) into the REAL `_build_stripped_injected_deltas` — the same
call `addon.py` makes. The resulting dual-log lines are then run through the REAL read-side
`accumulate_dual_log`, so the reported badge signal is the one the pane would compute.

The suppression is READ-SIDE ONLY (`parser._msgs_delta_is_substantial`): the delta entries
themselves are written unchanged, so the expanded view keeps rendering every span. This replay
therefore checks two separate things — that the written entries are byte-identical before/after
(they must be, the writer is untouched), and that the BADGE signal drops for the noise classes.

Why a dedicated replay: `dev/proxy_dual_log/verify_strip_inject.py` calls the delta builder
WITHOUT `all_ops`, so its message section produces no spans at all and it is structurally blind
to this change (independently, it raises KeyError 'spans' on current logs — `_diff_messages` no
longer emits that key; pre-existing, untouched). `dev/proxy_instrumentation/p2_badge_words_probe.py`
and `p3_badge_inline_probe.py` reference recorded sessions that no longer exist on disk.

`--baseline` restores the pre-fix badge behavior by monkeypatching `parser._msgs_delta_is_substantial`
to the old `bool(messages_delta)` rule, so both sides of the comparison run identical code otherwise.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem>
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem> --baseline
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem> --compare

`--compare` runs both modes in one process and diffs every entry byte-wise (json, sort_keys).
"""

# INFRASTRUCTURE
import argparse
import json
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
WORKTREE_ROOT = _SCRIPT_DIR.parents[1]
sys.path.insert(0, str(WORKTREE_ROOT))

# Recorded dual-logs are untracked data living in the main checkout, not duplicated into worktrees.
MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

# Lazy import — this module is imported both at top-level (WORKTREE_ROOT already on sys.path from
# the block above) and reused this way inside `_is_tt_msg`, mirroring `replay()`'s own late-import
# convention below (src imports deferred so this file can be inspected without src/ importable).
def _shape_classifier():
    from src.proxy_display.proxy_badge import _is_total_tokens_nuke_text
    return _is_total_tokens_nuke_text


# FUNCTIONS

def _load_jsonl(path: Path) -> list:
    entries = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


# True when the message is a genuine role='system' total_tokens marker OR the same marker preceded
# only by known CC nudge prose (2026-09-05, claude-f trailing-nudge widening) — delegates to the
# real `parser._is_total_tokens_nuke_text` rather than keeping a second, narrower copy of the shape
# test here, so this replay's own classification stays in agreement with the production code it is
# verifying against.
def _is_tt_msg(msg: dict) -> bool:
    if msg.get('role') != 'system':
        return False
    is_nuke_text = _shape_classifier()
    content = msg.get('content', '')
    if isinstance(content, str):
        return is_nuke_text(content)
    if isinstance(content, list):
        return (len(content) == 1 and isinstance(content[0], dict)
                and content[0].get('type') == 'text'
                and is_nuke_text(str(content[0].get('text', ''))))
    return False


# Replay every request of one session; returns list of (request_id, stripped_entry, injected_entry)
def replay(stem: str) -> list:
    from src.proxy import strip_inject_delta as sid
    from src.proxy.rules import apply_modification_rules

    if True:
        orig_entries = _load_jsonl(LOG_DIR / f'{stem}_original.jsonl')
        out = []
        prev_s = None
        prev_i = None
        for entry in orig_entries:
            orig_payload = entry.get('payload', {})
            if not orig_payload.get('messages'):
                continue
            model = entry.get('model', '') or orig_payload.get('model', '')
            family = 'haiku' if 'haiku' in model.lower() else ('sonnet' if 'sonnet' in model.lower() else 'opus')
            replayed = json.loads(json.dumps(orig_payload))
            result = apply_modification_rules(replayed, family, str(MAIN_REPO_ROOT), None)
            fwd_payload, all_ops = result[0], result[-1]
            rid = entry.get('request_id', '') or f'req{len(out)}'
            s_entry, i_entry, new_s, new_i = sid._build_stripped_injected_deltas(
                orig_payload, fwd_payload, rid, prev_s, prev_i, model, all_ops,
            )
            prev_s, prev_i = new_s, new_i
            s_entry['flow_id'] = rid
            i_entry['flow_id'] = rid
            out.append((rid, s_entry, i_entry, orig_payload))
        return out


# Run the REAL read-side accumulator over the replayed entries -> {flow_id: has_content}.
# baseline=True restores the pre-fix rule (any non-empty messages_delta badges).
def has_content_map(entries: list, which: int, baseline: bool = False) -> dict:  # noqa: C901
    from src.proxy_display import dual_log_accumulator as _accumulator
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log
    saved = _accumulator._msgs_delta_is_substantial
    if baseline:
        _accumulator._msgs_delta_is_substantial = lambda md, et: bool(md)
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
        for row in entries:
            f.write(json.dumps(row[which]) + '\n')
        tmp = Path(f.name)
    acc: dict = {}
    try:
        accumulate_dual_log(tmp, 0, acc)
    finally:
        tmp.unlink()
        _accumulator._msgs_delta_is_substantial = saved
    merged: dict = {}
    for fam in acc.values():
        merged.update(fam.get('_has_content_by_flow_id', {}))
    return merged


# {flow_id: set(msg_idx)} for one side, via the same real accumulator
def msg_idx_map(entries: list, which: int) -> dict:
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
        for row in entries:
            f.write(json.dumps(row[which]) + '\n')
        tmp = Path(f.name)
    acc: dict = {}
    try:
        accumulate_dual_log(tmp, 0, acc)
    finally:
        tmp.unlink()
    merged: dict = {}
    for fam in acc.values():
        merged.update(fam.get('_msg_idx_by_flow_id', {}))
    return merged


# The badge pair the REQ header actually renders, via the real parser.badge_flags
def badge_maps(entries: list) -> tuple:
    from src.proxy_display.proxy_badge import badge_flags
    hc_s = has_content_map(entries, 1)
    hc_i = has_content_map(entries, 2)
    mi_s = msg_idx_map(entries, 1)
    mi_i = msg_idx_map(entries, 2)
    strip_by_fid: dict = {}
    inject_by_fid: dict = {}
    for rid, _s, _i, _o in entries:
        entry = {
            'flow_id': rid,
            '_strip_fns_lookup': hc_s, '_inject_fns_lookup': hc_i,
            '_strip_msgs_lookup': mi_s, '_inject_msgs_lookup': mi_i,
        }
        strip_by_fid[rid], inject_by_fid[rid] = badge_flags(entry)
    return strip_by_fid, inject_by_fid


# Classify a request by what its ORIGINAL payload + baseline delta contained
def classify(base_s: dict, orig_payload: dict) -> str:
    md = base_s.get('messages_delta', {})
    if not md:
        return 'no_msg_delta'
    msgs = orig_payload.get('messages', [])
    tt_only = True
    has_tt = False
    for midx in md:
        i = int(midx)
        is_tt = i < len(msgs) and _is_tt_msg(msgs[i])
        has_tt = has_tt or is_tt
        tt_only = tt_only and is_tt
    if tt_only:
        return 'pure_total_tokens'
    return 'mixed' if has_tt else 'real_strip'


def _canon(entry: dict) -> str:
    return json.dumps({k: v for k, v in entry.items() if k != 'timestamp'}, sort_keys=True)


# ORCHESTRATOR

def compare_workflow(stem: str) -> int:
    rows = replay(stem)

    base_hc_s = has_content_map(rows, 1, baseline=True)
    base_hc_i = has_content_map(rows, 2, baseline=True)
    show_strip, show_inject = badge_maps(rows)

    buckets: dict = {}
    for rid, s_entry, _i_entry, orig_payload in rows:
        buckets.setdefault(classify(s_entry, orig_payload), []).append(rid)

    print(f'\ntt_delta_skip_replay — {stem}')
    print(f'  requests replayed: {len(rows)}\n')
    print('  classification (by written delta + original payload):')
    for cls in ('pure_total_tokens', 'mixed', 'real_strip', 'no_msg_delta'):
        print(f'    {cls:<20} {len(buckets.get(cls, []))}')

    md_s = sum(1 for r in rows if r[1].get('messages_delta'))
    md_i = sum(1 for r in rows if r[2].get('messages_delta'))
    print(f'\n  WRITE SIDE (must be unchanged by this fix — spans keep rendering):')
    print(f'    entries with messages_delta   stripped: {md_s}')
    print(f'    entries with messages_delta   injected: {md_i}')
    print(f'\n  RENDERED BADGE, old one-to-one rule -> new rule:')
    print(f'    `strip`  shown: {sum(base_hc_s.values())} -> {sum(show_strip.values())}')
    print(f'    `inject` shown: {sum(base_hc_i.values())} -> {sum(show_inject.values())}')

    tt_ids = set(buckets.get('pure_total_tokens', []))
    real_ids = set(buckets.get('real_strip', []))
    mixed_ids = set(buckets.get('mixed', []))

    # pure total_tokens: BOTH words off
    tt_quiet = sum(1 for r in tt_ids if not show_strip.get(r) and not show_inject.get(r))
    print(f'\n  pure_total_tokens requests with BOTH badge words off: {tt_quiet}/{len(tt_ids)}')
    # every other nuke / real strip: `strip` on, and `inject` on whenever a span was injected
    real_loud = sum(1 for r in real_ids if show_strip.get(r))
    # Implication, not equality: a green span in the messages MUST light `inject`. The converse
    # does not hold — a system-section injection (proxy rules into system[2]) legitimately lights
    # `inject` with no injected messages_delta at all, so equality would false-alarm on those.
    _inj_msg_flows = _flows_with_injected_msgs(rows)
    real_with_green = real_ids & _inj_msg_flows
    real_inj = sum(1 for r in real_with_green if show_inject.get(r))
    print(f'  real_strip requests showing `strip`: {real_loud}/{len(real_ids)}')
    print(f'  real_strip requests with a green message span showing `inject`: {real_inj}/{len(real_with_green)}')
    mixed_loud = sum(1 for r in mixed_ids if show_strip.get(r) and show_inject.get(r))
    print(f'  mixed requests showing BOTH words: {mixed_loud}/{len(mixed_ids)}')

    tt_spans_kept = sum(1 for rid, s_e, _i, _o in rows if rid in tt_ids and s_e.get('messages_delta'))
    print(f'  pure_total_tokens requests still carrying stripped spans: {tt_spans_kept}/{len(tt_ids)}')

    ok = (tt_quiet == len(tt_ids) and real_loud == len(real_ids)
          and real_inj == len(real_with_green) and mixed_loud == len(mixed_ids)
          and tt_spans_kept == len(tt_ids))
    print(f'\n{"PASS" if ok else "FAIL"}\n')
    return 0 if ok else 1


# flow_ids whose INJECTED side touched at least one message block (i.e. a span renders green there)
def _flows_with_injected_msgs(rows: list) -> set:
    return {rid for rid, _s, i_e, _o in rows if i_e.get('messages_delta')}


def single_workflow(stem: str) -> int:
    rows = replay(stem)
    md = sum(1 for r in rows if r[1].get('messages_delta'))
    show_strip, show_inject = badge_maps(rows)
    print(f'{stem}: {len(rows)} requests, {md} with stripped messages_delta, '
          f'{sum(show_strip.values())} showing `strip`, {sum(show_inject.values())} showing `inject`')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stem', help='log stem, e.g. api_requests_opus_monitor_cc_1788011077')
    ap.add_argument('--compare', action='store_true',
                    help='report the badge signal under the old rule vs the new one')
    args = ap.parse_args()
    if args.compare:
        sys.exit(compare_workflow(args.stem))
    sys.exit(single_workflow(args.stem))
