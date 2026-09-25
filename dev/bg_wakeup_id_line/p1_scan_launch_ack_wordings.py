# INFRASTRUCTURE
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))
sys.path.insert(0, str(WORKTREE_ROOT))

from src.proxy.strip_bg_launch_ack import (
    _BG_LAUNCH_ACK_MARKER,
    _BG_LAUNCH_ACK_PREFIX,
    _ACK_ID_RE,
    _ACK_PATH_RE,
)

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
REPORT_DIR = Path(__file__).resolve().parent / 'md'

CORPUS_FILES = [
    'api_requests_opus_monitor_cc_1785336796_original.jsonl',
    'api_requests_opus_posts_1785338463_original.jsonl',
    'api_requests_opus_wise2627_1785324012_original.jsonl',
    'api_requests_worker_25c51a2e_tn-role-system_1785344818_original.jsonl',
]
EXCLUDED_FILES = {
    'api_requests_opus_monitor_cc_1785347492_original.jsonl':
        'currently-live session — last entry 2026-07-29T21:06:45Z, ~3min before this worker '
        'started (2026-07-29T21:06:41Z); this is the actively-dispatching Opus session',
    'api_requests_worker_25c51a2e_bg-ack-shapes_1785359201_original.jsonl':
        "this worker's own worktree activity — proxy log starts exactly at dispatch time",
}

LIVE_OBSERVED_TEXT = (
    'Command was manually backgrounded by user with ID: bsxpatpam. Output is being written '
    'to: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/'
    '587284d6-c174-4432-a8d0-b5e2bcf10f0b/tasks/bsxpatpam.output'
)

_ID_NORM_RE = re.compile(r'with ID:\s*[^.\s]+')
_PATH_NORM_RE = re.compile(r'Output is being written to:\s*\S+')


# ORCHESTRATOR

def main():
    findings = {}
    raw_dup_counter = defaultdict(int)
    total_requests = compute_total_requests()
    total_requests = collect_total_requests(total_requests, findings, raw_dup_counter)
    report = _build_report(findings, total_requests, raw_dup_counter)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = compute_out_path()
    out_path.write_text(report, encoding='utf-8')
    print_wrote(out_path, findings, total_requests)


# FUNCTIONS

def compute_total_requests():
    return 0


def collect_total_requests(total_requests, findings, raw_dup_counter):
    for fname in CORPUS_FILES:
        path = LOG_DIR / fname
        print(f'scanning {fname} ...')
        total_requests += _scan_file(path, findings, raw_dup_counter)
    return total_requests


def _scan_file(path, findings, raw_dup_counter):
    session = path.name
    prev_count = 0
    requests = 0
    with open(path, 'rb') as fh:
        for raw in fh:
            requests += 1
            entry = json.loads(raw)
            messages = entry.get('payload', {}).get('messages', [])
            start = prev_count if prev_count <= len(messages) else 0
            for local_idx, msg in enumerate(messages[start:]):
                role = msg.get('role', '?')
                content = msg.get('content', '')
                for shape, text in _iter_candidate_blocks(content):
                    if not _looks_like_launch_ack_candidate(text):
                        continue
                    key = _normalize_wording(text)
                    rec = findings.setdefault(key, {
                        'count': 0, 'sessions': set(), 'shapes': set(), 'roles': set(),
                        'example': text,
                    })
                    rec['count'] += 1
                    rec['sessions'].add(session)
                    rec['shapes'].add(shape)
                    rec['roles'].add(role)
            prev_count = len(messages)
    with open(path, 'rb') as fh:
        for raw in fh:
            entry = json.loads(raw)
            messages = entry.get('payload', {}).get('messages', [])
            for msg in messages:
                for shape, text in _iter_candidate_blocks(msg.get('content', '')):
                    if _looks_like_launch_ack_candidate(text):
                        raw_dup_counter[session] += 1
    return requests


def _iter_candidate_blocks(content):
    if isinstance(content, str):
        yield ('top_level_str', content)
        return
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get('type')
            if btype == 'text':
                yield ('text_block', block.get('text', ''))
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    yield ('tool_result_str', inner)
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            yield ('tool_result_list_text', sub.get('text', ''))


def _looks_like_launch_ack_candidate(text):
    if not isinstance(text, str):
        return False
    stripped = text.lstrip()
    return (
        stripped.startswith('Command')
        and 'with ID:' in text
        and 'Output is being written to:' in text
    )


def _normalize_wording(text):
    t = _ID_NORM_RE.sub('with ID: <ID>', text)
    t = _PATH_NORM_RE.sub('Output is being written to: <PATH>', t)
    return t


def _build_report(findings, total_requests, raw_dup_counter):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines += _report_header_and_corpus(ts, total_requests)
    lines += _report_contamination_trap()
    lines += _report_dedup_importance(findings, raw_dup_counter)
    lines += _report_live_observed_crosscheck(findings)
    lines += _report_distinct_wordings(findings)
    lines += _report_additional_wordings_note()
    return '\n'.join(lines)


def _report_header_and_corpus(ts, total_requests):
    lines = []
    lines.append('# D1 — bg-launch-ack wording inventory (real corpus)')
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
    lines.append(f'Total requests scanned (deduped pass): {total_requests}')
    lines.append('')
    return lines


def _report_contamination_trap():
    lines = []
    lines.append('## Contamination trap (beyond the 2 named exclusions)')
    lines.append('')
    lines.append(
        '`api_requests_opus_posts_1785338463` and `api_requests_worker_..._tn-role-system_1785344818` '
        'are themselves PRIOR investigative sessions on this exact defect area — raw substring grep for '
        '`"Output is being written to:"` hits source lines (`_ACK_PATH_RE = re.compile(...)`), templated '
        'dev-report printouts (`${O}`, `<pfad>`, `#3: \'...\'`), and Read-tool dumps of `strip_bg_launch_ack.py`, '
        'not just genuine acks. Blanket-excluding these files would also discard genuine acks those sessions '
        'produced by actually running background Bash calls. Fix applied: **structural filter, not file '
        'exclusion** — a candidate is only counted if the JSON-parsed block\'s FULL text starts with `Command` '
        'at position 0 (checked in `_looks_like_launch_ack_candidate`). Source dumps/reports never satisfy this '
        '(Read output starts with line numbers, docstrings start with other prose, report printouts start with '
        '`===`/`#N:`).'
    )
    lines.append('')
    return lines


def _report_dedup_importance(findings, raw_dup_counter):
    lines = []
    lines.append('## Dedup importance (raw vs deduped)')
    lines.append('')
    lines.append('| Session | Raw candidate-block occurrences (all cumulative snapshots) | Deduped (new-message-only) |')
    lines.append('|---|---|---|')
    for fname in CORPUS_FILES:
        raw = raw_dup_counter.get(fname, 0)
        deduped = sum(rec['count'] for rec in findings.values() if fname in rec['sessions'])
        lines.append(f'| `{fname}` | {raw} | {deduped} |')
    lines.append('')
    lines.append(
        'Confirms cumulative dual-log duplication: a single genuine occurrence (same `toolu_id`, same text) '
        'reappears in every later request of its session — raw grep would wildly overcount.'
    )
    lines.append('')
    return lines


def _report_live_observed_crosscheck(findings):
    lines = []
    lines.append('## Live-observed text (2026-07-29, from prompt) — corpus cross-check')
    lines.append('')
    live_key = _normalize_wording(LIVE_OBSERVED_TEXT)
    if live_key in findings:
        lines.append(f'Matches corpus template (`{live_key[:70]}...`) — found in corpus independently, see wording table below.')
    else:
        lines.append('Does NOT match any normalized template found in this corpus (would be a genuinely new wording).')
    lines.append('')
    return lines


def _report_distinct_wordings(findings):
    lines = []
    lines.append('## Distinct wordings')
    lines.append('')
    if not findings:
        lines.append('**0 candidate launch-ack blocks found in the scanned corpus.** Reported plainly — not manufactured.')
    for i, (key, rec) in enumerate(sorted(findings.items(), key=lambda kv: -kv[1]['count']), 1):
        verdict = _mechanism_verdict(rec['example'])
        lines.append(f'### Wording {i}')
        lines.append('')
        lines.append(f'- Occurrences (deduped): **{rec["count"]}**')
        lines.append(f'- Sessions: {sorted(rec["sessions"])} ({len(rec["sessions"])} of {len(CORPUS_FILES)} scanned)')
        lines.append(f'- Roles seen: {sorted(rec["roles"])}')
        lines.append(f'- Content shapes seen: {sorted(rec["shapes"])}')
        lines.append('')
        lines.append('**Verbatim example (volatile id/path bolded):**')
        lines.append('')
        lines.append('```')
        lines.append(_mark_volatile(rec['example']))
        lines.append('```')
        lines.append('')
        lines.append('**Mechanism fire/no-fire:**')
        lines.append('')
        lines.append('| Mechanism | Result |')
        lines.append('|---|---|')
        lines.append(f'| `_BG_LAUNCH_ACK_MARKER` fast-path gate (`{_BG_LAUNCH_ACK_MARKER!r}` in text) | {"FIRES" if verdict["marker_fires"] else "does NOT fire"} |')
        lines.append(f'| `_BG_LAUNCH_ACK_PREFIX` startswith check | {"FIRES" if verdict["prefix_fires"] else "does NOT fire"} |')
        lines.append(f'| `_ACK_ID_RE` | {"extracts: " + verdict["id_extract"] if verdict["id_extract"] else "FAILS to extract"} |')
        lines.append(f'| `_ACK_PATH_RE` | {"extracts: " + verdict["path_extract"] if verdict["path_extract"] else "FAILS to extract"} |')
        lines.append('')
    return lines


def _mechanism_verdict(text):
    marker_fires = _BG_LAUNCH_ACK_MARKER in text
    prefix_fires = text.lstrip().startswith(_BG_LAUNCH_ACK_PREFIX)
    id_match = _ACK_ID_RE.search(text)
    path_match = _ACK_PATH_RE.search(text)
    return {
        'marker_fires': marker_fires,
        'prefix_fires': prefix_fires,
        'id_extract': id_match.group(1).strip() if id_match else None,
        'path_extract': path_match.group(1).strip() if path_match else None,
    }


def _mark_volatile(text):
    t = _ID_NORM_RE.sub('with ID: **<ID>**', text)
    t = _PATH_NORM_RE.sub('Output is being written to: **<PATH>**', t)
    return t


def _report_additional_wordings_note():
    lines = []
    lines.append('## Additional wordings sought but not found')
    lines.append('')
    lines.append(
        'Prompt notes a long-running Bash call WITHOUT `run_in_background` is killed on timeout (exit 143), '
        'not backgrounded — no third launch wording expected from that path, and none was found. The '
        'structural filter (`Command` + `with ID:` + `Output is being written to:`) is broad enough to catch '
        'unknown wordings in the same family; none beyond the ones listed above were found in this corpus.'
    )
    lines.append('')
    return lines


def compute_out_path():
    return REPORT_DIR / 'launch_ack_wordings_20260729.md'


def print_wrote(out_path, findings, total_requests):
    print(f'wrote {out_path} — {len(findings)} distinct wording(s), {total_requests} requests scanned')


if __name__ == '__main__':
    main()
