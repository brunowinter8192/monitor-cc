# INFRASTRUCTURE
import json
from pathlib import Path

from sysload.config import GROUP_KILLABLE, GROUPS


# ORCHESTRATOR

def diff_workflow(argv: list) -> int:
    before_path, after_path = parse_diff_args(argv)
    before, after = load_result(before_path), load_result(after_path)
    print(render_diff(before, after))
    return 0


# FUNCTIONS

def parse_diff_args(argv: list) -> tuple:
    if len(argv) != 2:
        raise SystemExit('usage: diff <before.json> <after.json>')
    return argv[0], argv[1]


def load_result(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def render_diff(before: dict, after: dict) -> str:
    return '\n'.join([
        render_system_delta(before['summary'], after['summary']),
        render_group_delta(before['summary'], after['summary']),
        render_action_outcomes(before, after),
        render_new_killables(before, after),
    ])


def render_system_delta(before: dict, after: dict) -> str:
    b, a = before['system'], after['system']
    return (
        f"load1 {b['load'][0]} -> {a['load'][0]}  mem free {b['mem_free_pct']}% -> {a['mem_free_pct']}%  "
        f"swap used {b['swap_used_mb']} -> {a['swap_used_mb']} MB  processes {before['process_total']} -> {after['process_total']}")


def render_group_delta(before: dict, after: dict) -> str:
    lines = []
    for group in GROUPS:
        lines.append(
            f"{group:<10} n {before['counts'][group]} -> {after['counts'][group]}  "
            f"cpu_now {before['cpu_now'][group]}% -> {after['cpu_now'][group]}%  "
            f"rss {before['rss_mb'][group]} -> {after['rss_mb'][group]} MB")
    return '\n'.join(lines)


def render_action_outcomes(before: dict, after: dict) -> str:
    if not before['actions']:
        return 'killable actions in the before snapshot: none'
    lines = ['killable actions from the before snapshot:']
    for action in before['actions']:
        lines.append(f"  {action['kind']} {action['target']}: {action_outcome(action, after)}")
    return '\n'.join(lines)


def action_outcome(action: dict, after: dict) -> str:
    for row in after['rows']:
        if action['kind'] == 'kill_pid' and row['pid'] == action['target'] and row['lstart'] == action['lstart']:
            return 'STILL RUNNING'
        if action['kind'] == 'tmux_kill_session' and row['facts'].get('session') == action['target']:
            return 'STILL PRESENT'
    return 'gone'


def render_new_killables(before: dict, after: dict) -> str:
    known = {(a['kind'], a['target']) for a in before['actions']}
    fresh = [a for a in after['actions'] if (a['kind'], a['target']) not in known]
    if not fresh:
        return 'no new killable actions after the run'
    lines = [f'new killable actions after the run ({GROUP_KILLABLE}, something respawned or appeared):']
    for a in fresh:
        lines.append(f"  {a['kind']} {a['target']} [{a['rule']}]")
    return '\n'.join(lines)
