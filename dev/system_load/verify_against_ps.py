# INFRASTRUCTURE
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPORT_DIR = Path(__file__).resolve().parent / 'md'
_FIREFOX_PREFIX = '/Applications/Firefox.app/Contents/MacOS/'
_MONITOR_PREFIX = 'monitor_cc_'
_TOP_N = 10


# ORCHESTRATOR

def verify_workflow() -> int:
    result = load_json(sys.argv[1])
    ps_rows = load_ps(sys.argv[2])
    lines = compare_all(result, ps_rows, read_tmux_sessions(), read_ps_cpu_top())
    write_report(lines)
    print('\n'.join(lines))
    return 0 if all(not line.startswith('FAIL') for line in lines) else 1


# FUNCTIONS

def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_ps(path: str) -> dict:
    rows = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            rows[int(parts[0])] = {'ppid': int(parts[1]), 'command': parts[2] if len(parts) > 2 else ''}
    return rows


def read_tmux_sessions() -> set:
    text = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'], capture_output=True, text=True).stdout
    return {line for line in text.splitlines() if line}


def read_ps_cpu_top() -> list:
    text = subprocess.run(['ps', '-A', '-r', '-o', 'pid=,%cpu='], capture_output=True, text=True).stdout
    return [int(line.split()[0]) for line in text.splitlines()[:_TOP_N]]


def compare_all(result: dict, ps_rows: dict, tmux_sessions: set, ps_top: list) -> list:
    rows = {r['pid']: r for r in result['rows']}
    return (
        compare_pid_sets(rows, ps_rows)
        + compare_parent_links(rows, ps_rows)
        + compare_firefox(rows, ps_rows)
        + compare_monitor_sessions(result, tmux_sessions)
        + compare_group_totals(result)
        + compare_top_cpu(rows, ps_top)
    )


def compare_pid_sets(rows: dict, ps_rows: dict) -> list:
    only_snapshot, only_ps = set(rows) - set(ps_rows), set(ps_rows) - set(rows)
    verdict = 'OK  ' if len(only_snapshot) + len(only_ps) <= 20 else 'FAIL'
    return [f'{verdict} pid sets: snapshot {len(rows)}, ps {len(ps_rows)}, only in snapshot {len(only_snapshot)}, only in ps {len(only_ps)} (churn between the two reads)']


def compare_parent_links(rows: dict, ps_rows: dict) -> list:
    common = set(rows) & set(ps_rows)
    wrong = [pid for pid in common if rows[pid]['ppid'] != ps_rows[pid]['ppid']]
    return [f"{'OK  ' if not wrong else 'FAIL'} parent links equal for {len(common)} shared pids, mismatches {len(wrong)}"]


def compare_firefox(rows: dict, ps_rows: dict) -> list:
    independent = {pid for pid, r in ps_rows.items() if r['command'].startswith(_FIREFOX_PREFIX)}
    from_snapshot = {pid for pid, r in rows.items() if r['rule'] == 'K2_firefox'}
    differing = independent ^ from_snapshot
    verdict = 'OK  ' if len(differing) <= 3 else 'FAIL'
    return [f'{verdict} firefox members: ps {len(independent)}, snapshot {len(from_snapshot)}, differing {len(differing)}']


def compare_monitor_sessions(result: dict, tmux_sessions: set) -> list:
    independent = {s for s in tmux_sessions if s.startswith(_MONITOR_PREFIX)}
    from_snapshot = {a['target'] for a in result['actions'] if a['kind'] == 'tmux_kill_session'}
    verdict = 'OK  ' if independent == from_snapshot else 'FAIL'
    return [f'{verdict} monitor sessions: tmux {sorted(independent)} vs actions {sorted(from_snapshot)}']


def compare_group_totals(result: dict) -> list:
    counts = result['summary']['counts']
    verdict = 'OK  ' if sum(counts.values()) == result['summary']['process_total'] == len(result['rows']) else 'FAIL'
    return [f'{verdict} group counts {counts} add up to {len(result["rows"])} rows']


def compare_top_cpu(rows: dict, ps_top: list) -> list:
    snapshot_top = [r['pid'] for r in sorted(rows.values(), key=lambda r: -r['cpu_now'])[:_TOP_N]]
    shared = len(set(snapshot_top) & set(ps_top))
    return [f'INFO top-{_TOP_N} CPU overlap between top(instant) and ps(decaying average): {shared}/{_TOP_N}; snapshot top {snapshot_top}; ps top {ps_top}']


def write_report(lines: list) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    body = '# verify_against_ps\n\nRun: ' + stamp + '\n\n' + '\n'.join(f'- {line}' for line in lines) + '\n'
    (_REPORT_DIR / 'verify_against_ps.md').write_text(body, encoding='utf-8')


if __name__ == '__main__':
    sys.exit(verify_workflow())
