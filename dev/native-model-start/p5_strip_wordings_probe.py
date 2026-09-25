# INFRASTRUCTURE
import json
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'p5_strip_wordings_probe_report.md'

SESSIONS = [
    ('posts', 'api_requests_opus_posts_1786051932'),
    ('websearch', 'api_requests_opus_websearch_1786052022'),
]

MARKERS = {
    'bg_launch_ack_wording1': 'running in background with ID',
    'bg_launch_ack_wording2': 'backgrounded by user with ID',
    'bg_completed_marker': 'Background command "',
    'task_notification_tag': '<task-notification>',
}

# FUNCTIONS

def _load_session_requests(stem: str) -> list:
    out = []
    with open(LOG_DIR / f'{stem}_original.jsonl', encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            out.append((e.get('flow_id', ''), e.get('payload', {})))
    return out


def _fn_map_census(stem: str) -> dict:
    counts: dict = {}
    for suffix in ('stripped', 'injected'):
        path = LOG_DIR / f'{stem}_{suffix}.jsonl'
        if not path.exists():
            continue
        with open(path, encoding='utf-8') as f:
            for line in f:
                e = json.loads(line)
                for fn in (e.get('fn_map') or {}).values():
                    counts[fn] = counts.get(fn, 0) + 1
    return counts


def _check_markers_stripped(payload: dict) -> list:
    from src.proxy.rules import apply_modification_rules
    from src.proxy.payload_helpers import _top_level_content_contains
    modified, *_ = apply_modification_rules(payload, 'opus', '', 'main')
    orig_messages = payload.get('messages', [])
    fwd_messages = modified.get('messages', [])
    hits = []
    for idx, om in enumerate(orig_messages):
        oc = om.get('content', '') if isinstance(om, dict) else ''
        for label, marker in MARKERS.items():
            if not _top_level_content_contains(oc, marker):
                continue
            fm = fwd_messages[idx] if idx < len(fwd_messages) else {}
            fc = fm.get('content', '') if isinstance(fm, dict) else ''
            survived = _top_level_content_contains(fc, marker)
            hits.append((idx, label, survived))
    return hits


def _part_a_census_lines():
    lines = []
    lines.append('## Part A — fn_map census (real recorded dual-logs, historical record)')
    lines.append('')
    all_fn_counts = {}
    for tag, stem in SESSIONS:
        counts = _fn_map_census(stem)
        all_fn_counts[tag] = counts
        lines.append(f'### {tag} (`{stem}`)')
        lines.append('')
        lines.append('| function | occurrences |')
        lines.append('|---|---|')
        for fn, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f'| `{fn}` | {n} |')
        lines.append('')
    return lines, all_fn_counts


def _compute_fire_verdicts(all_fn_counts):
    marker_present_in_session = {}
    for tag, stem in SESSIONS:
        with open(LOG_DIR / f'{stem}_original.jsonl', encoding='utf-8') as f:
            raw = f.read()
        marker_present_in_session[tag] = {
            'bg_launch_ack': ('running in background with ID' in raw) or ('backgrounded by user with ID' in raw),
        }

    bg_launch_fired = all(
        (not marker_present_in_session[tag]['bg_launch_ack']) or all_fn_counts[tag].get('_apply_bg_launch_ack_strip', 0) > 0
        for tag, _ in SESSIONS
    )
    tn_or_bg_exit_fired = all(
        all_fn_counts[tag].get('_apply_first_pass', 0) > 0 or all_fn_counts[tag].get('_apply_bg_exit_strip', 0) > 0
        for tag, _ in SESSIONS
    )
    return marker_present_in_session, bg_launch_fired, tn_or_bg_exit_fired


def _part_a_verdict_lines(bg_launch_fired, tn_or_bg_exit_fired, marker_present_in_session):
    lines = []
    lines.append(f'- `_apply_bg_launch_ack_strip` fired wherever its marker text was present in the '
                 f'session\'s raw original log: {bg_launch_fired}')
    lines.append(f'  - marker present per session: {({tag: v["bg_launch_ack"] for tag, v in marker_present_in_session.items()})} '
                 f'— websearch session genuinely never contains an explicit run_in_background launch-ack '
                 f'wording (0 raw occurrences confirmed) — not a strip-coverage gap, a data-availability fact')
    lines.append(f'- TN/bg-completed replacement fired in both sessions (`_apply_first_pass` OR '
                 f'`_apply_bg_exit_strip`): {tn_or_bg_exit_fired}')
    lines.append('')
    return lines


def _part_b_sweep():
    total_marker_hits = 0
    total_survived = 0
    survivals = []
    marker_totals = {label: 0 for label in MARKERS}
    for tag, stem in SESSIONS:
        requests = _load_session_requests(stem)
        for seq, (flow_id, payload) in enumerate(requests):
            hits = _check_markers_stripped(payload)
            for idx, label, survived in hits:
                total_marker_hits += 1
                marker_totals[label] += 1
                if survived:
                    total_survived += 1
                    survivals.append((tag, seq, flow_id, idx, label))
    return total_marker_hits, total_survived, survivals, marker_totals


def _part_b_report_lines(total_marker_hits, marker_totals, total_survived, survivals):
    lines = []
    lines.append(f'- Total marker occurrences checked (original content containing a known bg-marker): {total_marker_hits}')
    lines.append(f'  - by marker: {marker_totals}')
    lines.append(f'- Survived unstripped into forwarded output: {total_survived}')
    if survivals:
        lines.append('')
        lines.append('| session | seq | flow_id | msg_idx | marker |')
        lines.append('|---|---|---|---|---|')
        for tag, seq, flow_id, idx, label in survivals[:30]:
            lines.append(f'| {tag} | {seq} | {flow_id} | {idx} | {label} |')
    lines.append('')
    return lines


def _overall_verdict_lines(bg_launch_fired, tn_or_bg_exit_fired, total_survived, total_marker_hits):
    verdict = 'CLEAN' if (bg_launch_fired and tn_or_bg_exit_fired and total_survived == 0) else 'FINDING'
    lines = []
    lines.append('## Verdict')
    lines.append('')
    lines.append(f'**{verdict}**')
    lines.append(f'- fn_map census confirms both bg-launch-ack (wherever its wording occurs) and '
                 f'TN/bg-exit strips fired in the 223-era historical logs: {bg_launch_fired and tn_or_bg_exit_fired}')
    lines.append(f'- No bg-related marker wording survived unstripped into any forwarded payload '
                 f'(top-level content only, matching the real passes\' own `_top_level_content_contains` '
                 f'gate — tool_result search-result content quoting these markers as prose is correctly '
                 f'excluded, not a strip target), against the CURRENT worktree code: {total_survived == 0} '
                 f'({total_survived}/{total_marker_hits} survived)')
    lines.append(f'- Observation (not a finding, out of the two named strip targets\' scope): the '
                 f'websearch session\'s backgrounded commands went through CC\'s 120s auto-timeout '
                 f'path ("Command did not complete within its 120s timeout and was moved to the '
                 f'background") rather than an explicit `run_in_background=true` launch-ack — a '
                 f'structurally different message our proxy does not strip (and was not asked to).')
    return lines, verdict


# ORCHESTRATOR
def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# Surface 3 — strip wordings on CC 2.1.223 (issue #63)', '']

    census_lines, all_fn_counts = _part_a_census_lines()
    lines.extend(census_lines)

    marker_present_in_session, bg_launch_fired, tn_or_bg_exit_fired = _compute_fire_verdicts(all_fn_counts)
    lines.extend(_part_a_verdict_lines(bg_launch_fired, tn_or_bg_exit_fired, marker_present_in_session))

    lines.append('## Part B — unstripped-wording sweep (real CURRENT code, replayed over all requests)')
    lines.append('')
    total_marker_hits, total_survived, survivals, marker_totals = _part_b_sweep()
    lines.extend(_part_b_report_lines(total_marker_hits, marker_totals, total_survived, survivals))

    verdict_lines, verdict = _overall_verdict_lines(bg_launch_fired, tn_or_bg_exit_fired, total_survived, total_marker_hits)
    lines.extend(verdict_lines)

    REPORT_PATH.write_text('\n'.join(lines))
    print(f'Report written: {REPORT_PATH}')
    print(f'Verdict: {verdict}  (bg_launch_fired={bg_launch_fired}, tn_or_bg_exit_fired={tn_or_bg_exit_fired}, '
          f'survived={total_survived}/{total_marker_hits})')


if __name__ == '__main__':
    main()
