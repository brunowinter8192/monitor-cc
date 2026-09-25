# INFRASTRUCTURE
import json
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))
from src.proxy.rules import apply_modification_rules
from src.proxy.diff_engine import compose_block, _get_inner_text

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'p4_dual_log_integrity_probe_report.md'

SESSIONS = [
    ('posts', 'api_requests_opus_posts_1786051932'),
    ('websearch', 'api_requests_opus_websearch_1786052022'),
]

KNOWN_CONTENT_BLOCK_TYPES = {'text', 'tool_use', 'tool_result', 'thinking'}
KNOWN_PAYLOAD_KEYS = {
    'model', 'max_tokens', 'system', 'tools', 'messages', 'output_config',
    'anthropic_beta', 'context_management', 'diagnostics', 'metadata', 'stream',
    'temperature', 'top_p', 'top_k', 'stop_sequences',
}
INITIAL_TOTAL_CHECKS = 0


# ORCHESTRATOR

def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = compute_lines()

    total_checks = INITIAL_TOTAL_CHECKS
    failures = []
    keys_seen, sys_shapes_seen, block_types_seen = set(), set(), set()
    sample_payload_by_key: dict = {}

    total_checks = collect_total_checks(keys_seen, sys_shapes_seen, block_types_seen, sample_payload_by_key, lines, total_checks, failures)

    part_a_lines, total_fail_inv1, total_fail_inv2 = _part_a_verdict_lines(total_checks, failures)
    lines.extend(part_a_lines)

    part_b_lines, new_keys, new_block_types = _part_b_schema_lines(keys_seen, sys_shapes_seen, block_types_seen)
    lines.extend(part_b_lines)

    pass_through_lines, pass_through_results = _pass_through_section_lines(new_keys, sample_payload_by_key)
    lines.extend(pass_through_lines)

    verdict_lines, verdict, keys_dropped = _overall_verdict_lines(
        total_fail_inv1, total_fail_inv2, total_checks, new_keys, new_block_types, pass_through_results)
    lines.extend(verdict_lines)

    REPORT_PATH.write_text('\n'.join(lines))
    print_report_written()
    print_verdict(verdict, total_fail_inv1, total_fail_inv2, total_checks, new_keys, keys_dropped, new_block_types)


# FUNCTIONS

def compute_lines():
    return ['# Surface 2 — dual_log integrity + schema drift (issue #63, CC 2.1.223)', '']


def collect_total_checks(keys_seen, sys_shapes_seen, block_types_seen, sample_payload_by_key, lines, total_checks, failures):
    for tag, stem in SESSIONS:
        session_lines, session_checks, session_failures = _process_session(
            tag, stem, keys_seen, sys_shapes_seen, block_types_seen, sample_payload_by_key)
        lines.extend(session_lines)
        total_checks += session_checks
        failures.extend(session_failures)
    return total_checks


def _process_session(tag, stem, keys_seen, sys_shapes_seen, block_types_seen, sample_payload_by_key):
    requests = _load_session_requests(stem)
    lines = []
    lines.append(f'## Session: {tag} (`{stem}`, {len(requests)} requests)')
    lines.append('')
    session_checks = 0
    session_fail = 0
    failures = []
    for seq, (flow_id, payload) in enumerate(requests):
        checks, _all_ops = _check_composition(payload)
        _scan_schema(payload, keys_seen, sys_shapes_seen, block_types_seen)
        for k in payload.keys():
            if k not in KNOWN_PAYLOAD_KEYS and k not in sample_payload_by_key:
                sample_payload_by_key[k] = payload
        for msg_idx, blk_idx, ok1, ok2 in checks:
            session_checks += 1
            if not ok1:
                session_fail += 1
                failures.append((tag, seq, flow_id, msg_idx, blk_idx, 'Inv1'))
            if not ok2:
                session_fail += 1
                failures.append((tag, seq, flow_id, msg_idx, blk_idx, 'Inv2'))
    lines.append(f'- Composition checks (blocks with recorded ops): {session_checks}')
    lines.append(f'- Failures: {session_fail}')
    lines.append('')
    return lines, session_checks, failures


def _load_session_requests(stem: str) -> list:
    path = LOG_DIR / f'{stem}_original.jsonl'
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            out.append((e.get('flow_id', ''), e.get('payload', {})))
    return out


def _check_composition(payload: dict) -> tuple:

    result = apply_modification_rules(payload, 'opus', '', 'main')
    modified_payload, _mods, _os2, _smi, _smo, _smr, _ima, all_ops = result
    orig_messages = payload.get('messages', [])
    fwd_messages = modified_payload.get('messages', [])

    checks = []
    for msg_idx, blk_map in (all_ops or {}).items():
        for blk_idx, block_ops in blk_map.items():
            om = orig_messages[msg_idx] if msg_idx < len(orig_messages) else {}
            fm = fwd_messages[msg_idx] if msg_idx < len(fwd_messages) else {}
            oc = om.get('content', '') if isinstance(om, dict) else ''
            fc = fm.get('content', '') if isinstance(fm, dict) else ''
            if isinstance(oc, list):
                ob = oc[blk_idx] if blk_idx < len(oc) else None
                c0 = _get_inner_text(ob) if ob is not None else ''
            else:
                c0 = oc if isinstance(oc, str) and blk_idx == 0 else ''
            if isinstance(fc, list):
                fb = fc[blk_idx] if blk_idx < len(fc) else None
                cfwd = _get_inner_text(fb) if fb is not None else ''
            else:
                cfwd = fc if isinstance(fc, str) and blk_idx == 0 else ''
            spans = compose_block(c0, block_ops)
            recon_c0 = ''.join(t for tag, t in spans if tag in ('equal', 'stripped'))
            recon_fwd = ''.join(t for tag, t in spans if tag in ('equal', 'injected'))
            ok1 = recon_c0 == c0
            ok2 = recon_fwd == cfwd
            checks.append((msg_idx, blk_idx, ok1, ok2))
    return checks, all_ops


def _scan_schema(payload: dict, keys_seen: set, sys_shapes_seen: set, block_types_seen: set) -> None:
    keys_seen.update(payload.keys())
    for b in payload.get('system', []) or []:
        if isinstance(b, dict):
            sys_shapes_seen.add(tuple(sorted(b.keys())))
    for msg in payload.get('messages', []) or []:
        content = msg.get('content') if isinstance(msg, dict) else None
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict):
                    block_types_seen.add(blk.get('type', '<no-type>'))


def _part_a_verdict_lines(total_checks, failures):
    total_fail_inv1 = sum(1 for f in failures if f[-1] == 'Inv1')
    total_fail_inv2 = sum(1 for f in failures if f[-1] == 'Inv2')
    lines = []
    lines.append('## Part A verdict — composition invariant')
    lines.append('')
    lines.append(f'Total blocks checked across both sessions: {total_checks}')
    lines.append(f'Inv1 (C0 reconstruction) failures: {total_fail_inv1}')
    lines.append(f'Inv2 (Cfwd reconstruction) failures: {total_fail_inv2}')
    if failures:
        lines.append('')
        lines.append('| session | seq | flow_id | msg_idx | blk_idx | invariant |')
        lines.append('|---|---|---|---|---|---|')
        for tag, seq, flow_id, msg_idx, blk_idx, inv in failures[:30]:
            lines.append(f'| {tag} | {seq} | {flow_id} | {msg_idx} | {blk_idx} | {inv} |')
    lines.append('')
    return lines, total_fail_inv1, total_fail_inv2


def _part_b_schema_lines(keys_seen, sys_shapes_seen, block_types_seen):
    lines = []
    lines.append('## Part B — schema drift')
    lines.append('')
    new_keys = keys_seen - KNOWN_PAYLOAD_KEYS
    new_block_types = block_types_seen - KNOWN_CONTENT_BLOCK_TYPES
    lines.append(f'- Top-level payload keys observed: {sorted(keys_seen)}')
    lines.append(f'  - NOT in the pipeline\'s explicitly-named set: {sorted(new_keys) or "(none)"}')
    lines.append(f'- System-block key-shapes observed: {sorted(sys_shapes_seen)}')
    lines.append(f'- Content-block `type` values observed: {sorted(block_types_seen)}')
    lines.append(f'  - NOT in message_summary.py\'s known set: {sorted(new_block_types) or "(none)"}')
    lines.append('')
    return lines, new_keys, new_block_types


def _pass_through_section_lines(new_keys, sample_payload_by_key):
    pass_through_results = {}
    lines = []
    if new_keys:
        pass_through_results = _verify_unknown_keys_pass_through(new_keys, sample_payload_by_key)
        lines.append('### Pass-through verification for unmodeled top-level keys')
        lines.append('')
        lines.append('`apply_modification_rules`/`cache.py` build the modified payload via '
                      '`dict(payload)` (shallow copy) + selective overwrite of `system`/`messages`/'
                      '`tools` — any key not explicitly touched forwards byte-identical by '
                      'construction. Verified directly per key below (not assumed):')
        lines.append('')
        lines.append('| key | forwarded unchanged | sample value |')
        lines.append('|---|---|---|')
        for key, (match, sample) in pass_through_results.items():
            lines.append(f'| `{key}` | {match} | `{sample}` |')
        lines.append('')
    return lines, pass_through_results


def _verify_unknown_keys_pass_through(new_keys: set, requests_by_key: dict) -> dict:
    results = {}
    for key in new_keys:
        payload = requests_by_key.get(key)
        if payload is None:
            results[key] = (None, 'never found isolated')
            continue
        modified, *_ = apply_modification_rules(payload, 'opus', '', 'main')
        results[key] = (modified.get(key) == payload.get(key), repr(payload.get(key))[:150])
    return results


def _overall_verdict_lines(total_fail_inv1, total_fail_inv2, total_checks, new_keys, new_block_types,
                            pass_through_results):
    keys_dropped = [k for k, (match, _s) in pass_through_results.items() if match is False]
    composition_clean = total_fail_inv1 == 0 and total_fail_inv2 == 0
    schema_clean = not new_block_types and not keys_dropped
    verdict = 'CLEAN' if (composition_clean and schema_clean) else 'FINDING'
    lines = []
    lines.append('## Verdict')
    lines.append('')
    lines.append(f'**{verdict}**')
    lines.append(f'- Composition invariant: {"CLEAN" if composition_clean else "FINDING"} '
                 f'({total_fail_inv1 + total_fail_inv2} failures / {total_checks} checks)')
    lines.append(f'- New top-level keys (`{sorted(new_keys)}`): CLEAN — not specially modeled, but '
                 f'verified byte-identical pass-through, not dropped'
                 if new_keys and not keys_dropped else
                 f'- New top-level keys: {sorted(new_keys) or "(none)"}'
                 + (f' — **DROPPED, real finding**: {keys_dropped}' if keys_dropped else ''))
    lines.append(f'- New content-block types: {"CLEAN (none)" if not new_block_types else f"FINDING: {sorted(new_block_types)} not in message_summary.py\'s handled set (falls through to its generic json.dumps summary — display-only gap, not a strip-pipeline correctness issue; composition invariant above already confirms no pass mishandles these blocks)"}')
    return lines, verdict, keys_dropped


def print_report_written():
    print(f'Report written: {REPORT_PATH}')


def print_verdict(verdict, total_fail_inv1, total_fail_inv2, total_checks, new_keys, keys_dropped, new_block_types):
    print(f'Verdict: {verdict}  (composition_failures={total_fail_inv1 + total_fail_inv2}/{total_checks}, '
          f'new_keys={sorted(new_keys)}, keys_dropped={keys_dropped}, new_block_types={sorted(new_block_types)})')


if __name__ == '__main__':
    main()
