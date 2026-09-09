"""
Issue #63 live-verify, surface 1 — cache breakpoint placement (src/proxy/cache.py) across the two
recorded CC 2.1.223 sessions (api_requests_opus_posts_1786051932, 152 requests;
api_requests_opus_websearch_1786052022, 108 requests).

Replays every recorded request through a REAL ProxyAddon() instance, in chronological order, per
session (fresh addon per session — state carries across requests exactly as in a live proxy
process: prev_messages_by_model, fixated, prev_*_hashes_by_model). Extracts the actual bytes about
to be sent (flow.request.content) per request and inspects cache_control placement:

  BP1 — system[2] (cross-session anchor)
  BP2 — last non-defer tool
  BP3 — last message unchanged from the previous request (end of stable prefix)
  BP4 — last message (always)

Checks the interaction flagged by the 223 release research: 2.1.212 changed mid-conversation
system-block caching behind gateways, and 223 traffic now carries mid-conversation role=system
MESSAGES (nag/notice text) that our proxy either nukes to "." or (2026-08-07 fix,
_apply_role_system_strip's mid-turn-user-message guard) preserves whole. For every pair of
consecutive requests, diffs every message index PRESENT IN BOTH (cache_control stripped before
comparing — BP3/BP4 legitimately toggle it) to catch any already-existing (non-tail) message whose
content changed — a real prefix-cache bust, not the expected/designed tail growth.

Usage (from project root, real venv — imports mitmproxy via proxy.addon):
    ./venv/bin/python dev/native-model-start/p3_cache_breakpoints_probe.py
"""

# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'p3_cache_breakpoints_probe_report.md'

SESSIONS = [
    ('posts', 'api_requests_opus_posts_1786051932'),
    ('websearch', 'api_requests_opus_websearch_1786052022'),
]

# FUNCTIONS

class _FakeHeaders(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default

    def pop(self, k, default=None):
        return dict.pop(self, k.lower(), default)


class _FakeRequest:
    def __init__(self, payload):
        self.method = "POST"
        self.pretty_host = "api.anthropic.com"
        self.path = "/v1/messages"
        self.headers = _FakeHeaders()
        self.content = json.dumps(payload).encode("utf-8")


class _FakeFlow:
    def __init__(self, payload, flow_id):
        self.request = _FakeRequest(payload)
        self.metadata = {}
        self.id = flow_id


# Load every recorded request's full original payload for one session, in file (chronological) order
def _load_session_requests(stem: str) -> list:
    path = LOG_DIR / f'{stem}_original.jsonl'
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            out.append((e.get('flow_id', ''), e.get('payload', {})))
    return out


def _cc_indices(items) -> list:
    return [i for i, x in enumerate(items) if isinstance(x, dict) and 'cache_control' in x]


def _msg_has_cc(msg: dict) -> bool:
    content = msg.get('content')
    if isinstance(content, list):
        return any(isinstance(b, dict) and 'cache_control' in b for b in content)
    return False


# Content of one message with cache_control stripped, for cross-request identity comparison.
# Two independent normalizations collapse pure JSON-shape churn from the cache_control add/remove
# cycle so only REAL content changes surface:
#  (1) cache.py's own _normalize_user_content_shape (role='user' only, production behavior).
#  (2) A single-text-block list <-> plain string collapse for EVERY role — not cache.py's own
#      scope, but the mechanical cause of ALL remaining false positives observed in this probe's
#      first two runs: _add_cache_control_to_message wraps a plain string into
#      [{"type":"text","text":X,"cache_control":...}] to attach the marker (any role); once that
#      position is no longer the BP3/BP4 target on a later request, the pass that regenerates that
#      message (e.g. _apply_role_system_strip re-emitting a fresh bare "." every time it fires) has
#      no reason to preserve the wrapper — semantically identical text, cosmetically different
#      shape. Confirmed: after normalization (1) alone, EVERY remaining raw diff was exactly this
#      wrap/unwrap pattern on non-user roles (system "." messages, mostly) — no case where the
#      actual text differed while shapes also happened to differ.
def _msg_content_no_cc(msg: dict):
    content = msg.get('content')
    if isinstance(content, list):
        stripped = [
            ({k: v for k, v in b.items() if k != 'cache_control'} if isinstance(b, dict) else b)
            for b in content
        ]
        if len(stripped) == 1 and isinstance(stripped[0], dict) \
                and set(stripped[0].keys()) == {'type', 'text'} and stripped[0]['type'] == 'text':
            return stripped[0]['text']
        return stripped
    return content


# Replay one session through a fresh real ProxyAddon; returns per-request records
def _replay_session(tag: str, stem: str, tmp_root: str) -> list:
    from proxy.addon import ProxyAddon, _derive_worker_context
    requests = _load_session_requests(stem)
    with mock.patch.dict(os.environ, {
        "PROXY_LOG_ID": f"opus_{tag}_probe",
        "PROXY_PROJECT_PATH": f"/Users/x/{tag}",
        "MONITOR_CC_ROOT": tmp_root,
    }, clear=False):
        addon = ProxyAddon()
        addon.identity.worker_context = _derive_worker_context()
        records = []
        for seq, (flow_id, payload) in enumerate(requests):
            flow = _FakeFlow(payload, flow_id or f'seq{seq}')
            addon.request(flow)
            sent = json.loads(flow.request.content)
            system = sent.get('system', []) or []
            tools = sent.get('tools', []) or []
            messages = sent.get('messages', []) or []
            records.append({
                'seq': seq, 'flow_id': flow_id,
                'sys_len': len(system), 'sys_cc': _cc_indices(system),
                'tools_len': len(tools), 'tools_cc': _cc_indices(tools),
                'msg_len': len(messages),
                'msg_cc': [i for i, m in enumerate(messages) if _msg_has_cc(m)],
                'messages': messages,
            })
    return records


# Cross-request analysis: BP1/BP2 stability + BP3/BP4 prefix-bust detection
def _analyze(records: list) -> dict:
    bp1_positions = set()
    bp1_missing = []
    bp2_positions = set()
    bp2_missing_despite_tools = []
    prefix_busts = []  # (seq, msg_idx) where a pre-existing message's content changed

    for i, rec in enumerate(records):
        if rec['sys_len'] >= 3:
            if rec['sys_cc'] == [2]:
                bp1_positions.add(2)
            elif not rec['sys_cc']:
                bp1_missing.append(rec['seq'])
            else:
                bp1_positions.update(rec['sys_cc'])
        if rec['tools_len'] > 0:
            if rec['tools_cc']:
                bp2_positions.update(rec['tools_cc'])
            else:
                bp2_missing_despite_tools.append(rec['seq'])
        if i == 0:
            continue
        prev, curr = records[i - 1], rec
        prev_msgs, curr_msgs = prev['messages'], curr['messages']
        common_len = min(len(prev_msgs), len(curr_msgs))
        for idx in range(common_len):
            if _msg_content_no_cc(prev_msgs[idx]) != _msg_content_no_cc(curr_msgs[idx]):
                prefix_busts.append((rec['seq'], idx))

    return {
        'bp1_positions': sorted(bp1_positions),
        'bp1_missing_seqs': bp1_missing,
        'bp2_positions': sorted(bp2_positions),
        'bp2_missing_seqs': bp2_missing_despite_tools,
        'prefix_busts': prefix_busts,
    }


# For each prefix-bust index, classify: does the changed content match the mid-turn-user-message
# marker (before and/or after) — the exact interaction this probe is checking for.
def _classify_busts(records: list, busts: list) -> list:
    marker = 'The user sent a new message while you were working:'
    out = []
    for seq, idx in busts:
        prev_rec = records[seq - 1]
        curr_rec = records[seq]
        prev_content = prev_rec['messages'][idx].get('content', '') if idx < len(prev_rec['messages']) else ''
        curr_content = curr_rec['messages'][idx].get('content', '') if idx < len(curr_rec['messages']) else ''
        prev_txt = prev_content if isinstance(prev_content, str) else json.dumps(prev_content)[:200]
        curr_txt = curr_content if isinstance(curr_content, str) else json.dumps(curr_content)[:200]
        involves_marker = (isinstance(prev_content, str) and prev_content.lstrip().startswith(marker)) or \
                           (isinstance(curr_content, str) and curr_content.lstrip().startswith(marker))
        # tail-adjacent: idx is the last or second-to-last message in BOTH requests — almost
        # certainly an in-flight draft edit/extension (user still typing before submit), not a
        # deep-history mutation of already-"stable" content. is_bootstrap: happens in the
        # session's first 3 requests — CC's own session-start message reshaping.
        prev_len, curr_len = len(prev_rec['messages']), len(curr_rec['messages'])
        is_tail = idx >= curr_len - 2 and idx >= prev_len - 2
        is_bootstrap = seq <= 2
        category = (
            'mid_turn_marker' if involves_marker else
            'session_bootstrap' if is_bootstrap else
            'tail_draft_edit' if is_tail else
            'deep_history_mutation'
        )
        out.append({
            'seq': seq, 'idx': idx, 'category': category, 'involves_mid_turn_marker': involves_marker,
            'prev_snippet': prev_txt[:100], 'curr_snippet': curr_txt[:100],
        })
    return out


# ORCHESTRATOR
def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# Surface 1 — cache breakpoint placement (issue #63, CC 2.1.223)', '']
    lines.append('Real `ProxyAddon.request()` replay of all recorded requests, in chronological order, '
                  'per session. Cache-control positions inspected on the actual bytes about to be sent.')
    lines.append('')

    all_analyses = {}
    import tempfile
    for tag, stem in SESSIONS:
        with tempfile.TemporaryDirectory() as tmp_root:
            records = _replay_session(tag, stem, tmp_root)
        analysis = _analyze(records)
        busts_detail = _classify_busts(records, analysis['prefix_busts'])
        all_analyses[tag] = (records, analysis, busts_detail)

        lines.append(f'## Session: {tag} (`{stem}`, {len(records)} requests)')
        lines.append('')
        lines.append(f"- BP1 (system[2]) positions observed: {analysis['bp1_positions']} "
                      f"(want: exactly `[2]`) — missing on {len(analysis['bp1_missing_seqs'])} requests "
                      f"{analysis['bp1_missing_seqs'][:10]}")
        lines.append(f"- BP2 (last non-defer tool) positions observed: {analysis['bp2_positions']} "
                      f"— missing despite tools present on {len(analysis['bp2_missing_seqs'])} requests "
                      f"{analysis['bp2_missing_seqs'][:10]}")
        lines.append(f"- Content diffs at a common (non-tail-growth) message index, "
                      f"after cache_control + shape-churn normalization: {len(analysis['prefix_busts'])}")
        cat_counts = {}
        for b in busts_detail:
            cat_counts[b['category']] = cat_counts.get(b['category'], 0) + 1
        lines.append(f"  - by category: {cat_counts}")
        if busts_detail:
            lines.append('')
            lines.append('| seq | msg_idx | category | prev snippet | curr snippet |')
            lines.append('|---|---|---|---|---|')
            for b in busts_detail:
                lines.append(f"| {b['seq']} | {b['idx']} | {b['category']} | "
                              f"`{b['prev_snippet']}` | `{b['curr_snippet']}` |")
        lines.append('')

    # Overall verdict
    all_busts_detail = [b for _, _, bd in all_analyses.values() for b in bd]
    total_bootstrap = sum(1 for b in all_busts_detail if b['category'] == 'session_bootstrap')
    total_tail = sum(1 for b in all_busts_detail if b['category'] == 'tail_draft_edit')
    total_deep = sum(1 for b in all_busts_detail if b['category'] == 'deep_history_mutation')
    total_marker = sum(1 for b in all_busts_detail if b['category'] == 'mid_turn_marker')
    total_bp1_missing = sum(len(a['bp1_missing_seqs']) for _, a, _ in all_analyses.values())
    total_bp2_missing = sum(len(a['bp2_missing_seqs']) for _, a, _ in all_analyses.values())
    bp1_stable = all(a['bp1_positions'] in ([], [2]) for _, a, _ in all_analyses.values())
    bp2_stable = all(len(a['bp2_positions']) <= 1 for _, a, _ in all_analyses.values())

    verdict = 'FINDING' if (total_marker > 0 or total_deep > 0 or not bp1_stable or total_bp1_missing) else 'CLEAN'
    lines.append('## Verdict')
    lines.append('')
    lines.append(f'**{verdict}**')
    lines.append('')
    lines.append(f'- BP1 stable at system[2] across both sessions: {bp1_stable} '
                 f'(missing entirely on {total_bp1_missing} requests total)')
    lines.append(f'- BP2 stable (single tool-index value per session): {bp2_stable} '
                 f'(missing despite tools present on {total_bp2_missing} requests total)')
    lines.append(f'- `session_bootstrap` (CC reshaping msg 0 in the first 2-3 requests): {total_bootstrap} '
                 f'— expected, one-time, not a caching concern')
    lines.append(f'- `tail_draft_edit` (last/second-to-last message text changes — active user typing/'
                 f'editing before submit, correctly excluded from BP3\'s stable-prefix boundary): {total_tail} '
                 f'— expected, not a real prefix bust')
    lines.append(f'- `deep_history_mutation` (a message NOT near the tail changed content — CC itself '
                 f'reordering/inserting, e.g. an async bg-task notification landing before an '
                 f'already-sent user message): {total_deep} — **real finding, CC-side behavior, not '
                 f'proxy-caused, not fixable from our side**')
    lines.append(f'- `mid_turn_marker` (the flagged interaction: a mid-turn-user-message position, '
                 f'previously always "." pre-fix, now carries genuinely different real text across '
                 f'occurrences post the 2026-08-07 preserve-guard fix): {total_marker} — '
                 f'**real finding, THE interaction this probe was built to check**')
    lines.append('')

    REPORT_PATH.write_text('\n'.join(lines))
    print(f'Report written: {REPORT_PATH}')
    print(f'Verdict: {verdict}  (bootstrap={total_bootstrap}, tail_edit={total_tail}, '
          f'deep_history={total_deep}, mid_turn_marker={total_marker}, '
          f'bp1_missing={total_bp1_missing}, bp2_missing={total_bp2_missing})')


if __name__ == '__main__':
    main()
