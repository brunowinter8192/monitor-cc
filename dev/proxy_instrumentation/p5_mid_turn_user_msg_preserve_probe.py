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
REPORT_PATH = REPORT_DIR / 'mid_turn_user_msg_preserve_probe_report.md'

POSTS_STEM = 'api_requests_opus_posts_1786051932'
WEBSEARCH_STEM = 'api_requests_opus_websearch_1786052022'


# ORCHESTRATOR

def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        _check_preserve_case(),
        _check_noise_still_stripped(
            'deferred_tools_still_stripped', 'fa0ba243-86b1-47ef-aa32-fa9a9a384c38', 1,
            'The following deferred tools are now available via ToolSearch',
        ),
        _check_noise_still_stripped(
            'task_tools_nag_still_stripped', '9f02e2cd-209d-45a8-b98b-d06fcaf117c9', 33,
            "The task tools haven't been used recently",
        ),
        _check_noise_still_stripped(
            'date_changed_still_stripped', '1216af75-a704-4bfe-9448-921ac6ef8075', 49,
            'The date has changed.',
        ),
    ]
    lines = ['# Mid-turn user message preserve-guard probe (issue #61, CC 2.1.223)', '']
    lines.append(f'Preserve case session: `{POSTS_STEM}`. Regression-noise session: `{WEBSEARCH_STEM}`.')
    lines.append('')
    lines.append('| case | pass | detail |')
    lines.append('|---|---|---|')
    all_pass = True
    for r in results:
        all_pass = all_pass and r['ok']
        lines.append(f"| {r['label']} | {'PASS' if r['ok'] else 'FAIL'} | {r['detail']} |")
    lines.append('')
    lines.append(f"## Overall: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
    REPORT_PATH.write_text('\n'.join(lines))
    print(f'Report written: {REPORT_PATH}')
    for r in results:
        print(('PASS' if r['ok'] else 'FAIL'), r['label'], '-', r['detail'])
    print('ALL PASS' if all_pass else 'FAILURES PRESENT')
    sys.exit(0 if all_pass else 1)


# FUNCTIONS

def _check_preserve_case() -> dict:
    from src.proxy.message_passes import _apply_role_system_strip
    flow_id = '4b4d396b-a26e-4b44-ac32-144763cc786b'
    msg_idx = 274
    messages = _load_messages_for_flow(POSTS_STEM, flow_id)
    original_content = messages[msg_idx]['content']
    new_messages, mods, removed, changed_idxs, _injected, ops = _apply_role_system_strip(messages)
    result_content = new_messages[msg_idx]['content']
    ok = (
        result_content == original_content
        and 'jetzt' in result_content
        and result_content.startswith('The user sent a new message while you were working:')
        and msg_idx not in changed_idxs
        and msg_idx not in removed
        and msg_idx not in ops
    )
    return {
        'label': 'msg274_mid_turn_user_msg_preserved', 'ok': ok,
        'detail': f"role={new_messages[msg_idx].get('role')!r}, content_len={len(result_content)}, "
                  f"'jetzt' present={'jetzt' in result_content}, untouched={result_content == original_content}, "
                  f"changed_idxs contains 274={msg_idx in changed_idxs}",
    }


def _load_messages_for_flow(stem: str, flow_id: str) -> list:
    path = LOG_DIR / f'{stem}_original.jsonl'
    with open(path, encoding='utf-8') as f:
        for line in f:
            e = json.loads(line)
            if e.get('flow_id', '') == flow_id:
                return e['payload']['messages']
    raise AssertionError(f'flow_id {flow_id} not found in {path}')


def _check_noise_still_stripped(label: str, flow_id: str, msg_idx: int, expected_prefix: str) -> dict:
    from src.proxy.message_passes import _apply_role_system_strip
    messages = _load_messages_for_flow(WEBSEARCH_STEM, flow_id)
    original_content = messages[msg_idx]['content']
    new_messages, mods, _removed, changed_idxs, _injected, _ops = _apply_role_system_strip(messages)
    result_content = new_messages[msg_idx]['content']
    ok = (
        original_content.startswith(expected_prefix)
        and result_content == '.'
        and msg_idx in changed_idxs
        and 'stripped_role_system_msg' in mods
    )
    return {
        'label': label, 'ok': ok,
        'detail': f"orig_prefix_match={original_content.startswith(expected_prefix)}, "
                  f"result={result_content!r}, changed_idxs contains {msg_idx}={msg_idx in changed_idxs}",
    }


if __name__ == '__main__':
    main()
