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
REPORT_PATH = REPORT_DIR / 'blocklist_223_probe_report.md'

EXPECTED_KEPT = {'Bash', 'Read', 'Skill'}
NEWLY_BLOCKED = {'Artifact', 'ReportFindings', 'DeferredToolPlaceholder'}

# FUNCTIONS

def _select_session_stem() -> str:
    candidates = [
        p for p in sorted(LOG_DIR.glob('*_original.jsonl'))
        if not p.name.startswith('api_requests_worker_')
        and (LOG_DIR / p.name.replace('_original.jsonl', '_forwarded.jsonl')).exists()
    ]
    if not candidates:
        raise AssertionError(f'no main-session original+forwarded log pair found in {LOG_DIR}')
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        with open(path, encoding='utf-8') as f:
            for line in f:
                if json.loads(line).get('payload', {}).get('tools'):
                    return path.name[:-len('_original.jsonl')]
    raise AssertionError(f'no candidate log has a non-empty tools payload in {LOG_DIR}')


def _load_original_payload(stem: str) -> dict:
    path = LOG_DIR / f'{stem}_original.jsonl'
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            if e.get('payload', {}).get('tools'):
                return e['payload']
    raise AssertionError(f'no line with non-empty tools in {path}')


def _invoked_tool_names(stem: str) -> set:
    path = LOG_DIR / f'{stem}_original.jsonl'
    names = set()
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            for msg in e.get('payload', {}).get('messages', []):
                content = msg.get('content', '')
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if isinstance(blk, dict) and blk.get('type') == 'tool_use':
                        names.add(blk.get('name', ''))
    return names


def _forwarded_tool_names(stem: str) -> set:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    fwd_path = LOG_DIR / f'{stem}_forwarded.jsonl'
    entries, _ = _parse_forwarded_log(fwd_path, 0, {})
    names = set()
    for e in entries:
        names.update(e.get('tools_names', []))
    return names


def _run_checks(stem: str) -> list:
    from proxy.tools import _strip_unused_tools
    from constants import TOOL_BLOCKLIST

    payload = _load_original_payload(stem)
    orig_names = {t.get('name') for t in payload.get('tools', [])}
    modified, removed, removed_names = _strip_unused_tools(payload)
    kept_names = {t.get('name') for t in modified['tools']}
    mcp_names = {n for n in kept_names if n.startswith('mcp__')}
    non_mcp_kept = kept_names - mcp_names
    r1_ok = non_mcp_kept == EXPECTED_KEPT
    results = [(
        'post_strip_set_is_exact', r1_ok,
        f'orig={sorted(orig_names)} kept={sorted(kept_names)} '
        f'(non-MCP kept: {sorted(non_mcp_kept)}, want {sorted(EXPECTED_KEPT)}, mcp_extra={sorted(mcp_names)})',
    )]

    r2_ok = NEWLY_BLOCKED <= set(removed_names)
    results.append((
        'newly_blocked_actually_removed', r2_ok,
        f'removed_names contains all of {sorted(NEWLY_BLOCKED)}: {r2_ok} (removed={sorted(removed_names)})',
    ))

    invoked = _invoked_tool_names(stem)
    live_hits = NEWLY_BLOCKED & invoked
    r3_ok = not live_hits
    results.append((
        'no_live_tool_use_for_newly_blocked', r3_ok,
        f'tool_use invocations of newly-blocked names in session messages: {sorted(live_hits) or "(none)"}',
    ))

    fwd_names = _forwarded_tool_names(stem)
    r4_ok = 'Agent' not in fwd_names
    results.append((
        'agent_absent_from_forwarded', r4_ok,
        f"'Agent' in forwarded tools_names (real pipeline, pre-existing blocklist entry): {'Agent' in fwd_names} "
        f'(forwarded union={sorted(fwd_names)}) — confirms strip fires; drill-down sighting was the '
        f'intentional whole-stripped display row, not a strip-path bug',
    ))

    r5_ok = TOOL_BLOCKLIST >= NEWLY_BLOCKED
    results.append((
        'blocklist_contains_new_entries', r5_ok,
        f'{sorted(NEWLY_BLOCKED)} subset of TOOL_BLOCKLIST: {r5_ok}',
    ))

    return results


def _write_report(stem: str, results: list) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['# CC 2.1.223 TOOL_BLOCKLIST extension probe', '']
    lines.append(f'Session (newest main-session log in live corpus): `{stem}`')
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


# ORCHESTRATOR
def main() -> None:
    stem = _select_session_stem()
    results = _run_checks(stem)
    _write_report(stem, results)


if __name__ == '__main__':
    main()
