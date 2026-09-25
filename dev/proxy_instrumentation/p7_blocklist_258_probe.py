# INFRASTRUCTURE
import json
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'
REPORT_PATH = REPORT_DIR / 'blocklist_258_probe_report.md'

EXPECTED_KEPT = {'Bash', 'Read', 'Skill'}
NEWLY_BLOCKED = {'SendFeedback', 'ListAgents'}
RW_BLOCKED = {'Edit', 'Write'}


# ORCHESTRATOR

def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    newest_log = _newest_main_session_log()
    results, n_scanned, modified, removed_names = _check_newly_blocked_extension(newest_log)
    results = update_results(results, modified, removed_names)
    _write_report(newest_log, n_scanned, results)


# FUNCTIONS

def _newest_main_session_log() -> Path:
    candidates = [p for p in _all_original_logs() if not p.name.startswith('api_requests_worker_')]
    if not candidates:
        raise AssertionError(f'no main-session _original.jsonl found in {LOG_DIR}')
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _all_original_logs() -> list:
    return sorted(LOG_DIR.glob('*_original.jsonl'))


def _check_newly_blocked_extension(newest_log: Path) -> tuple:
    from src.proxy.tools import _strip_unused_tools
    from src.constants import TOOL_BLOCKLIST

    payload = _load_original_payload(newest_log)
    orig_names = {t.get('name') for t in payload.get('tools', [])}
    modified, removed, removed_names = _strip_unused_tools(payload)
    kept_names = {t.get('name') for t in modified['tools']}
    mcp_names = {n for n in kept_names if n.startswith('mcp__')}
    non_mcp_kept = kept_names - mcp_names
    r1_ok = non_mcp_kept == EXPECTED_KEPT
    results = [(
        'post_strip_set_is_exact', r1_ok,
        f'log={newest_log.name} orig={sorted(orig_names)} kept={sorted(kept_names)} '
        f'(non-MCP kept: {sorted(non_mcp_kept)}, want {sorted(EXPECTED_KEPT)}, mcp_extra={sorted(mcp_names)})',
    )]

    r2_ok = NEWLY_BLOCKED <= set(removed_names)
    results.append((
        'newly_blocked_actually_removed', r2_ok,
        f'removed_names contains all of {sorted(NEWLY_BLOCKED)}: {r2_ok} (removed={sorted(removed_names)})',
    ))

    all_logs = _all_original_logs()
    n_scanned, hits = _scan_corpus_for_live_tool_use(all_logs)
    r3_ok = not hits
    results.append((
        'no_live_tool_use_for_newly_blocked_corpus_wide', r3_ok,
        f'files scanned: {n_scanned}, tool_use hits for {sorted(NEWLY_BLOCKED)}: {len(hits)} '
        f'{("(" + str(hits) + ")") if hits else ""}',
    ))

    r4_ok = TOOL_BLOCKLIST >= NEWLY_BLOCKED
    results.append((
        'blocklist_contains_new_entries', r4_ok,
        f'{sorted(NEWLY_BLOCKED)} subset of TOOL_BLOCKLIST: {r4_ok}',
    ))

    return results, n_scanned, modified, removed_names


def _load_original_payload(path: Path) -> dict:
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            if e.get('payload', {}).get('tools'):
                return e['payload']
    raise AssertionError(f'no line with non-empty tools in {path}')


def _scan_corpus_for_live_tool_use(paths: list, target_names: set = NEWLY_BLOCKED) -> tuple:
    hits = []
    for path in paths:
        with open(path, encoding='utf-8') as f:
            for line in f:
                e = json.loads(line)
                for msg in e.get('payload', {}).get('messages', []):
                    content = msg.get('content', '')
                    if not isinstance(content, list):
                        continue
                    for blk in content:
                        if isinstance(blk, dict) and blk.get('type') == 'tool_use':
                            name = blk.get('name', '')
                            if name in target_names:
                                hits.append((path.name, name))
    return len(paths), hits


def update_results(results, modified, removed_names):
    results += _check_rw_extension(modified, removed_names)
    return results


def _check_rw_extension(modified: dict, removed_names: list) -> list:
    from src.constants import TOOL_BLOCKLIST


    r5_ok = RW_BLOCKED <= TOOL_BLOCKLIST
    results = [(
        'rw_blocklist_contains_new_entries', r5_ok,
        f'{sorted(RW_BLOCKED)} subset of TOOL_BLOCKLIST: {r5_ok}',
    )]

    r6_ok = RW_BLOCKED <= set(removed_names)
    results.append((
        'rw_actually_removed_from_representative_payload', r6_ok,
        f'removed_names contains all of {sorted(RW_BLOCKED)}: {r6_ok} (removed={sorted(removed_names)})',
    ))

    all_logs = _all_original_logs()
    n_scanned_rw, rw_hits = _scan_corpus_for_live_tool_use(all_logs, RW_BLOCKED)
    r7_ok = len(rw_hits) > 0
    rw_hit_files = sorted({fname for fname, _ in rw_hits})
    results.append((
        'rw_live_tool_use_present_corpus_wide_by_design', r7_ok,
        f'files scanned: {n_scanned_rw}, tool_use hits for {sorted(RW_BLOCKED)}: {len(rw_hits)} '
        f'across {len(rw_hit_files)} file(s) — UNLIKE checks 2/3 above, hits are EXPECTED here '
        f'(Edit/Write are among the dominant tools of every running session; this is the residual '
        f'risk documented for this milestone, not a bug)',
    ))

    r8_details = _rw_historic_tool_use_result_details()
    r8_ok = all(tu and tr for _, tu, tr in r8_details)
    results.append((
        'rw_historic_tool_use_result_left_untouched_documented_gap', r8_ok,
        f'for each of {sorted(RW_BLOCKED)}, a synthetic historic tool_use/tool_result pair '
        f'survives _strip_unused_tools + _strip_blocked_tool_references byte-for-byte: '
        f'{r8_details} (both functions only ever touch the tools schema array and '
        f'tool_reference content blocks — this pins the documented gap, it does not close it)',
    ))

    return results


def _rw_historic_tool_use_result_details() -> list:
    from src.proxy.tools import _strip_unused_tools
    from src.proxy.payload_helpers import _strip_blocked_tool_references

    r8_details = []
    for tool_name in sorted(RW_BLOCKED):
        historic_payload = _payload_with_historic_blocked_tool_use(tool_name)
        stripped_payload, _, _ = _strip_unused_tools(historic_payload)
        stripped_payload = _strip_blocked_tool_references(stripped_payload)
        assistant_msg = stripped_payload['messages'][1]
        result_msg = stripped_payload['messages'][2]
        tool_use_intact = assistant_msg['content'][0] == historic_payload['messages'][1]['content'][0]
        tool_result_intact = result_msg['content'][0] == historic_payload['messages'][2]['content'][0]
        r8_details.append((tool_name, tool_use_intact, tool_result_intact))
    return r8_details


def _payload_with_historic_blocked_tool_use(tool_name: str) -> dict:
    return {
        'model': 'claude-sonnet-5',
        'tools': [{'name': 'Bash', 'description': 'run bash'}],
        'messages': [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'read the file'}]},
            {'role': 'assistant', 'content': [
                {'type': 'tool_use', 'id': 'toolu_hist1', 'name': tool_name,
                 'input': {'file_path': '/tmp/x.txt'}},
            ]},
            {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': 'toolu_hist1', 'content': 'file contents'},
            ]},
        ],
    }


def _write_report(newest_log: Path, n_scanned: int, results: list) -> None:
    lines = ['# CC 2.1.258 + Edit/Write TOOL_BLOCKLIST extension probe', '']
    lines.append(f'Newest main-session log: `{newest_log.name}`')
    lines.append(f'Corpus files scanned for live tool_use: {n_scanned}')
    lines.append('')
    lines.append('| case | pass | detail |')
    lines.append('|---|---|---|')
    all_pass = True
    for label, ok, detail in results:
        all_pass = all_pass and ok
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} | {detail} |")
    lines.append('')
    lines.append(f"## Overall: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
    REPORT_PATH.write_text('\n'.join(lines))
    print(f'Report written: {REPORT_PATH}')
    for label, ok, detail in results:
        print(('PASS' if ok else 'FAIL'), label, '-', detail)
    print('ALL PASS' if all_pass else 'FAILURES PRESENT')
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
