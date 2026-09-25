# INFRASTRUCTURE
from sysload.config import (
    GROUP_DOUBTFUL, GROUP_ESSENTIAL, GROUP_KILLABLE, REPORT_HOT_CPU_NOW_PERCENT, REPORT_HOT_RSS_MB,
)

_OWNER_ROWS_SHOWN = 8


# FUNCTIONS

def render_report(result: dict, json_path: str) -> str:
    sections = [
        render_summary(result['summary']),
        render_owner_load(result['summary']),
        render_actions(result['actions']),
        render_doubtful(result['rows']),
        render_hot_essential(result['rows']),
        f'snapshot json: {json_path}',
    ]
    return '\n\n'.join(sections)


def render_summary(summary: dict) -> str:
    system = summary['system']
    counts, cpu, rss = summary['counts'], summary['cpu_now'], summary['rss_mb']
    lines = [
        f"load avg {system['load'][0]} {system['load'][1]} {system['load'][2]}  cores {system['ncpu']}  "
        f"mem free {system['mem_free_pct']}%  swap used {system['swap_used_mb']} MB  processes {summary['process_total']}",
    ]
    for group in (GROUP_KILLABLE, GROUP_DOUBTFUL, GROUP_ESSENTIAL):
        lines.append(f"{group:<10} n={counts[group]:<4} cpu_now={cpu[group]:>6}%  rss={rss[group]:>9} MB")
    return '\n'.join(lines)


def render_owner_load(summary: dict) -> str:
    items = list(summary['cpu_by_owner'].items())[:_OWNER_ROWS_SHOWN]
    return 'CPU now by owner kind: ' + ', '.join(f'{kind} {value}%' for kind, value in items)


def render_actions(actions: list) -> str:
    if not actions:
        return 'KILLABLE actions: none'
    lines = ['KILLABLE actions (exact target only):']
    for i, a in enumerate(actions, 1):
        stamp = a.get('lstart') or a.get('created')
        lines.append(
            f"  K{i:<2} {a['kind']:<18} {str(a['target']):<40} {a['rule']:<22} "
            f"procs={len(a['covers']):<3} cpu={a['cpu_now']:>5}% rss={a['rss_mb']:>7} MB  stamp={stamp}")
    return '\n'.join(lines)


def render_doubtful(rows: list) -> str:
    doubtful = [r for r in rows if r['group'] == GROUP_DOUBTFUL]
    if not doubtful:
        return 'DOUBTFUL: none'
    lines = ['DOUBTFUL (agent interprets, user decides):']
    for i, r in enumerate(doubtful, 1):
        lines.append(
            f"  D{i:<2} pid={r['pid']:<6} cpu={r['cpu_now']:>5}% rss={r['rss_mb']:>7} MB age={format_age(r['age_s']):>8} "
            f"{r['owner']}  {r['name']}  [{r['rule']}] {r['reason']}")
        lines.extend(render_fact_lines(r))
    return '\n'.join(lines)


def render_fact_lines(row: dict) -> list:
    facts = row['facts']
    lines = []
    if row['chain']:
        lines.append(f"        chain: {' < '.join(row['chain'])}")
    if facts.get('cwd'):
        lines.append(f"        cwd: {facts['cwd']}")
    for f in facts.get('task_files', []):
        lines.append(f"        task file: {f['path']} size={f['size']} last_write={format_age(f['mtime_age_s'])} ago")
    return lines


def render_hot_essential(rows: list) -> str:
    hot = [r for r in rows if r['group'] == GROUP_ESSENTIAL
           and (r['cpu_now'] >= REPORT_HOT_CPU_NOW_PERCENT or r['rss_mb'] >= REPORT_HOT_RSS_MB)]
    if not hot:
        return 'ESSENTIAL above the report thresholds: none'
    lines = ['ESSENTIAL above the report thresholds (not actionable):']
    for r in hot:
        lines.append(
            f"      pid={r['pid']:<6} cpu={r['cpu_now']:>5}% rss={r['rss_mb']:>7} MB {r['owner']}  {r['name']}  [{r['rule']}]")
    return '\n'.join(lines)


def format_age(seconds: float) -> str:
    seconds = int(seconds)
    if seconds >= 86400:
        return f'{seconds // 86400}d{seconds % 86400 // 3600}h'
    if seconds >= 3600:
        return f'{seconds // 3600}h{seconds % 3600 // 60}m'
    if seconds >= 60:
        return f'{seconds // 60}m{seconds % 60}s'
    return f'{seconds}s'
