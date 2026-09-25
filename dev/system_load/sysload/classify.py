# INFRASTRUCTURE
import os
import re
from typing import Optional

from sysload.config import (
    ACTION_PID, ACTION_TMUX_SESSION, ANCESTRY_MAX_HOPS, BGSHELL_STALE_AGE_SECONDS,
    CHAIN_MAX_ENTRIES, COMMAND_MAX_CHARS, DOUBTFUL_ALWAYS_NAMES,
    DOUBTFUL_ALWAYS_PATH_PARTS, DOUBTFUL_BURN_MIN_CPU_SECONDS, DOUBTFUL_BURN_RATIO,
    DOUBTFUL_CPU_NOW_PERCENT, DOUBTFUL_RSS_MB, ESSENTIAL_NAMES, ESSENTIAL_PATH_PARTS,
    GROUP_DOUBTFUL, GROUP_ESSENTIAL, GROUP_KILLABLE, GROUPS, KILLABLE_APP_PREFIXES,
    MAIN_PROXY_MARKER, MINERU_BIN_SUFFIXES, MINERU_ENTRY_ARGUMENT,
    MINERU_ENTRY_SCRIPT, MINERU_MODULE_TOKEN, MINERU_ROOTS, MONITOR_SESSION_PREFIX,
    REPORT_HOT_CPU_NOW_PERCENT, SYSTEM_PATH_PREFIXES, TASKS_BASE, TMUX_NAME,
    USER_APP_PATH_PREFIXES, WORKER_PROXY_MARKER, WORKER_SESSION_PREFIX,
)

_WORKER_PROXY_RE = re.compile(re.escape(WORKER_PROXY_MARKER) + r'(.+)_\d+_\d+\.py$')
_MAIN_PROXY_RE = re.compile(re.escape(MAIN_PROXY_MARKER) + r'([0-9a-f]+)_(\d+)_\d+\.py$')
_PORT_FLAG = '-p'
_SCRIPT_FLAG = '-s'


# FUNCTIONS

def classify_snapshot(snap: dict) -> dict:
    ctx = build_context(snap)
    rows = [classify_process(proc, ctx) for proc in snap['procs']]
    rows.sort(key=lambda r: (-r['cpu_now'], -r['rss_mb']))
    return {
        'taken_at': snap['taken_at'],
        'summary': summarize(snap, rows),
        'actions': build_actions(rows),
        'rows': rows,
    }


def build_context(snap: dict) -> dict:
    by_pid = {p['pid']: p for p in snap['procs']}
    ctx = {
        'snap': snap,
        'by_pid': by_pid,
        'children': index_children(snap['procs']),
        'tmux_ok': snap['tmux']['ok'],
        'session_created': {s['name']: s['created'] for s in snap['tmux']['sessions']},
        'pane_map': {p['pane_pid']: p['session'] for p in snap['tmux']['panes']},
        'holders': index_holders(snap['task_files']),
        'claude_pids': {p['pid'] for p in snap['procs'] if is_claude(p['command'])},
        'session_cache': {},
    }
    ctx['session_of'] = {p['pid']: resolve_session(p['pid'], ctx) for p in snap['procs']}
    ctx['claude_sessions'] = {ctx['session_of'][pid] for pid in ctx['claude_pids']} - {None}
    ctx['caller_pids'] = caller_chain(snap['self_pid'], ctx)
    ctx['caller_sessions'] = {ctx['session_of'].get(pid) for pid in ctx['caller_pids']} - {None}
    ctx['protected'] = find_protected(snap, ctx)
    ctx['firefox'] = {p['pid'] for p in snap['procs'] if firefox_app(p['command'])}
    return ctx


def index_children(procs: list) -> dict:
    children = {}
    for p in procs:
        children.setdefault(p['ppid'], []).append(p['pid'])
    return children


def index_holders(task_files: list) -> dict:
    holders = {}
    for f in task_files:
        holders.setdefault(f['pid'], []).append(f)
    return holders


def ancestors(pid: int, by_pid: dict) -> list:
    chain = []
    current = by_pid.get(pid)
    while current is not None and len(chain) < 64:
        parent = by_pid.get(current['ppid'])
        if parent is None or parent['pid'] == current['pid']:
            break
        chain.append(parent['pid'])
        current = parent
    return chain


def descendants(pid: int, children: dict) -> set:
    found, frontier = set(), [pid]
    while frontier:
        for child in children.get(frontier.pop(), []):
            if child not in found:
                found.add(child)
                frontier.append(child)
    return found


def resolve_session(pid: int, ctx: dict) -> Optional[str]:
    if pid in ctx['pane_map']:
        return ctx['pane_map'][pid]
    for ancestor in ancestors(pid, ctx['by_pid']):
        if ancestor in ctx['pane_map']:
            return ctx['pane_map'][ancestor]
    return None


def caller_chain(self_pid: int, ctx: dict) -> set:
    return {self_pid} | set(ancestors(self_pid, ctx['by_pid']))


def find_protected(snap: dict, ctx: dict) -> set:
    roots = set(snap.get('protect_pids', []))
    roots |= {p['pid'] for p in snap['procs'] if is_mineru_root(p, snap)}
    protected = set(roots)
    for pid in roots:
        protected |= descendants(pid, ctx['children'])
    return protected


def mineru_roots(snap: dict) -> tuple:
    return tuple(MINERU_ROOTS) + tuple(snap.get('protect_roots', []))


def is_mineru_root(proc: dict, snap: dict) -> bool:
    tokens = proc['command'].split()
    return is_convert_command(tokens, proc['pid'], snap) or is_mineru_bin_command(tokens, snap)


def is_convert_command(tokens: list, pid: int, snap: dict) -> bool:
    roots = mineru_roots(snap)
    for i, token in enumerate(tokens[:-1]):
        if tokens[i + 1] != MINERU_ENTRY_ARGUMENT:
            continue
        if any(token == f'{root}/{MINERU_ENTRY_SCRIPT}' for root in roots):
            return True
        if token == MINERU_ENTRY_SCRIPT and snap['cwds'].get(pid) in roots:
            return True
    return False


def is_mineru_bin_command(tokens: list, snap: dict) -> bool:
    roots = mineru_roots(snap)
    exact_bins = {f'{root}{suffix}' for root in roots for suffix in MINERU_BIN_SUFFIXES}
    return any(t in exact_bins or t == MINERU_MODULE_TOKEN for t in tokens[:4])


def cwd_candidate_pids(procs: list) -> list:
    return [p['pid'] for p in procs if is_claude(p['command']) or has_convert_shape(p['command'])]


def has_convert_shape(command: str) -> bool:
    tokens = command.split()
    return any(os.path.basename(t) == MINERU_ENTRY_SCRIPT and tokens[i + 1] == MINERU_ENTRY_ARGUMENT
               for i, t in enumerate(tokens[:-1]))


def is_claude(command: str) -> bool:
    tokens = command.split()
    if not tokens:
        return False
    return os.path.basename(tokens[0]) in ('claude', 'claude.exe') or '/claude/versions/' in tokens[0]


def firefox_app(command: str) -> Optional[str]:
    for app, prefix in KILLABLE_APP_PREFIXES.items():
        if command.startswith(prefix):
            return app
    return None


def classify_process(proc: dict, ctx: dict) -> dict:
    facts = collect_facts(proc, ctx)
    group, rule, reason, action = decide(proc, ctx, facts)
    return build_row(proc, ctx, facts, group, rule, reason, action)


def collect_facts(proc: dict, ctx: dict) -> dict:
    pid = proc['pid']
    facts = {'tty': proc['tty'], 'session': ctx['session_of'].get(pid)}
    cwd = ctx['snap']['cwds'].get(pid)
    if cwd:
        facts['cwd'] = cwd
    holds = ctx['holders'].get(pid)
    if holds:
        facts['task_files'] = [
            {'path': f['path'], 'size': f['size'], 'mtime_age_s': f['mtime_age_s']} for f in holds]
    return facts


def decide(proc: dict, ctx: dict, facts: dict) -> tuple:
    for rule in (
        rule_caller, rule_protected, rule_system, rule_firefox, rule_session,
        rule_proxy, rule_claude, rule_holder, rule_named_heavy, rule_load,
    ):
        verdict = rule(proc, ctx, facts)
        if verdict is not None:
            return verdict
    return GROUP_ESSENTIAL, 'quiet', 'below every load threshold', None


def rule_caller(proc, ctx, facts):
    if proc['pid'] in ctx['caller_pids']:
        return GROUP_ESSENTIAL, 'caller_chain', 'ancestor of the process running this tool', None
    if facts['session'] is not None and facts['session'] in ctx['caller_sessions']:
        return GROUP_ESSENTIAL, 'caller_session', 'inside the tmux session that runs this tool', None
    return None


def rule_protected(proc, ctx, facts):
    if proc['pid'] in ctx['protected']:
        return GROUP_ESSENTIAL, 'protected', 'part of the protected heavy job tree', None
    return None


def rule_system(proc, ctx, facts):
    command = proc['command']
    tokens = command.split()
    first = tokens[0] if tokens else ''
    if proc['pid'] == 1 or proc['uid'] != ctx['snap']['uid']:
        return GROUP_ESSENTIAL, 'system_owner', 'root or another user owns it', None
    if command.startswith(USER_APP_PATH_PREFIXES):
        return None
    if command.startswith(SYSTEM_PATH_PREFIXES) or os.path.basename(first) in ESSENTIAL_NAMES:
        return GROUP_ESSENTIAL, 'system_path', 'macOS system component', None
    if any(part in command for part in ESSENTIAL_PATH_PARTS):
        return GROUP_ESSENTIAL, 'core_app', 'terminal or menubar host', None
    if os.path.basename(first) == TMUX_NAME and proc['ppid'] == 1:
        return GROUP_ESSENTIAL, 'tmux_server', 'tmux server; kill its sessions instead', None
    return None


def rule_firefox(proc, ctx, facts):
    app = firefox_app(proc['command'])
    if app is None:
        return None
    main_pid = firefox_main_pid(proc['pid'], ctx)
    return GROUP_KILLABLE, 'K2_firefox', f'{app} process tree', pid_action(main_pid, ctx)


def firefox_main_pid(pid: int, ctx: dict) -> int:
    current = pid
    while ctx['by_pid'][current]['ppid'] in ctx['firefox']:
        current = ctx['by_pid'][current]['ppid']
    return current


def rule_session(proc, ctx, facts):
    session = facts['session']
    if not ctx['tmux_ok'] or session is None:
        return None
    if session.startswith(MONITOR_SESSION_PREFIX):
        return GROUP_KILLABLE, 'K1_monitor_session', 'monitor pane, restartable', session_action(session, ctx)
    if session.startswith(WORKER_SESSION_PREFIX) and session not in ctx['claude_sessions']:
        return GROUP_KILLABLE, 'K3_dead_worker_session', 'worker session without a Claude process', session_action(session, ctx)
    return None


def rule_proxy(proc, ctx, facts):
    script = flag_value(proc['command'].split(), _SCRIPT_FLAG)
    if script is None or os.path.basename(proc['command'].split()[0]) != 'mitmdump':
        return None
    name = os.path.basename(script)
    worker = _WORKER_PROXY_RE.search(name)
    if worker:
        return worker_proxy_verdict(proc, ctx, worker.group(1))
    main = _MAIN_PROXY_RE.search(name)
    if main:
        return main_proxy_verdict(proc, ctx, int(main.group(2)))
    return None


def worker_proxy_verdict(proc: dict, ctx: dict, name: str) -> tuple:
    if proc['ppid'] != 1:
        return GROUP_ESSENTIAL, 'proxy_owned', 'worker proxy with a live parent', None
    if not ctx['tmux_ok']:
        return GROUP_DOUBTFUL, 'proxy_unverified', 'tmux unreadable, worker liveness unknown', None
    if any(s.startswith(WORKER_SESSION_PREFIX) and s.endswith(f'-{name}') for s in ctx['session_created']):
        return GROUP_ESSENTIAL, 'proxy_live_worker', f'proxy of live worker {name}', None
    clients = client_count(proc, ctx)
    if clients is None:
        return GROUP_DOUBTFUL, 'proxy_unverified', f'worker {name} is gone, connection state unreadable', None
    if clients == 0:
        return GROUP_KILLABLE, 'K4_stale_proxy', f'worker {name} is gone and no client is connected', pid_action(proc['pid'], ctx)
    return GROUP_DOUBTFUL, 'proxy_clients_left', f'worker {name} is gone but {clients} connections remain', None


def main_proxy_verdict(proc: dict, ctx: dict, launcher_pid: int) -> tuple:
    if proc['ppid'] != 1 and proc['ppid'] in ctx['by_pid']:
        return GROUP_ESSENTIAL, 'proxy_owned', 'main-session proxy with a live parent', None
    return GROUP_DOUBTFUL, 'proxy_parentless', f'main-session proxy without its launcher {launcher_pid}', None


def client_count(proc: dict, ctx: dict) -> Optional[int]:
    port = flag_value(proc['command'].split(), _PORT_FLAG)
    if port is None or ctx['snap']['established'] is None:
        return None
    prefixes = (f'[::1]:{port}->', f'127.0.0.1:{port}->', f'localhost:{port}->')
    return sum(1 for name in ctx['snap']['established'] if name.startswith(prefixes))


def flag_value(tokens: list, flag: str) -> Optional[str]:
    for i, token in enumerate(tokens[:-1]):
        if token == flag:
            return tokens[i + 1]
    return None


def rule_claude(proc, ctx, facts):
    if proc['pid'] not in ctx['claude_pids']:
        return None
    return GROUP_DOUBTFUL, 'D_claude', claude_reason(proc, facts), None


def claude_reason(proc: dict, facts: dict) -> str:
    place = facts['session'] or (f"tty {proc['tty']}" if proc['tty'] != '??' else 'no tty, no tmux')
    return f'Claude Code process ({place}); only the user knows if the session is needed'


def rule_holder(proc, ctx, facts):
    files = ctx['holders'].get(proc['pid'])
    if not files:
        return None
    verdict = holder_class(proc['pid'], ctx)
    if verdict == 'orphan':
        return GROUP_KILLABLE, 'K5_bg_orphan', 'holds a task output file, no Claude ancestor', pid_action(proc['pid'], ctx)
    if verdict == 'unknown':
        return GROUP_DOUBTFUL, 'holder_unresolved', 'holds a task output file, ancestry unresolved', None
    if proc['age_s'] >= BGSHELL_STALE_AGE_SECONDS:
        return GROUP_DOUBTFUL, 'D_stale_bgshell', 'Claude background shell running long', None
    return GROUP_ESSENTIAL, 'bgshell_fresh', 'young Claude background shell', None


def holder_class(pid: int, ctx: dict) -> str:
    current = pid
    for _ in range(ANCESTRY_MAX_HOPS):
        if current in ctx['claude_pids']:
            return 'live'
        if current == 1:
            return 'orphan'
        proc = ctx['by_pid'].get(current)
        if proc is None:
            return 'unknown'
        current = proc['ppid']
    return 'unknown'


def rule_named_heavy(proc, ctx, facts):
    tokens = proc['command'].split()
    first = tokens[0] if tokens else ''
    if os.path.basename(first) in DOUBTFUL_ALWAYS_NAMES or any(part in proc['command'] for part in DOUBTFUL_ALWAYS_PATH_PARTS):
        return GROUP_DOUBTFUL, 'D_named_heavy', 'known heavy consumer, never auto-killed', None
    return None


def rule_load(proc, ctx, facts):
    cpu_now = ctx['snap']['cpu_now'].get(proc['pid'], 0.0)
    rss_mb = proc['rss_kb'] / 1024.0
    if cpu_now >= DOUBTFUL_CPU_NOW_PERCENT:
        return GROUP_DOUBTFUL, 'D_cpu_now', f'{cpu_now:.1f}% CPU right now', None
    if rss_mb >= DOUBTFUL_RSS_MB:
        return GROUP_DOUBTFUL, 'D_rss', f'{rss_mb:.0f} MB resident', None
    if proc['cpu_s'] >= DOUBTFUL_BURN_MIN_CPU_SECONDS and burn_ratio(proc) >= DOUBTFUL_BURN_RATIO:
        return GROUP_DOUBTFUL, 'D_burn', f'{burn_ratio(proc) * 100:.1f}% of one core averaged over its life', None
    return None


def burn_ratio(proc: dict) -> float:
    return proc['cpu_s'] / proc['age_s'] if proc['age_s'] > 0 else 0.0


def pid_action(pid: int, ctx: dict) -> dict:
    return {'kind': ACTION_PID, 'target': pid, 'lstart': ctx['by_pid'][pid]['lstart']}


def session_action(session: str, ctx: dict) -> dict:
    return {'kind': ACTION_TMUX_SESSION, 'target': session, 'created': ctx['session_created'].get(session)}


def build_row(proc: dict, ctx: dict, facts: dict, group: str, rule: str, reason: str, action: Optional[dict]) -> dict:
    pid = proc['pid']
    return {
        'pid': pid,
        'ppid': proc['ppid'],
        'name': short_name(proc['command']),
        'command': proc['command'][:COMMAND_MAX_CHARS],
        'age_s': proc['age_s'],
        'cpu_s': proc['cpu_s'],
        'cpu_now': ctx['snap']['cpu_now'].get(pid, 0.0),
        'rss_mb': round(proc['rss_kb'] / 1024.0, 1),
        'lstart': proc['lstart'],
        'owner': owner_of(proc, ctx, facts, rule),
        'chain': chain_of(pid, ctx),
        'group': group,
        'rule': rule,
        'reason': reason,
        'action': action,
        'facts': facts,
    }


def short_name(command: str) -> str:
    tokens = command.split()
    if not tokens:
        return '?'
    name = os.path.basename(tokens[0])
    if name.lower() in ('python', 'python3', 'node') and len(tokens) > 1:
        script = next((t for t in tokens[1:] if not t.startswith('-')), None)
        if script:
            return f'{name} {os.path.basename(script)}'
    return name


def chain_of(pid: int, ctx: dict) -> list:
    parents = [p for p in ancestors(pid, ctx['by_pid']) if p != 1]
    return [f"{short_name(ctx['by_pid'][p]['command'])}({p})" for p in parents[:CHAIN_MAX_ENTRIES]]


def owner_of(proc: dict, ctx: dict, facts: dict, rule: str) -> str:
    session = facts['session']
    if rule in ('protected',):
        return 'job:mineru'
    if rule.startswith('K2'):
        return 'app:Firefox'
    if rule in ('D_named_heavy',):
        return f'app:{short_name(proc["command"])}'
    if 'task_files' in facts:
        return f"bgshell:{encoded_project(facts['task_files'][0]['path'])}"
    if session is not None:
        return owner_of_session(session)
    if proc['pid'] in ctx['claude_pids']:
        return f"claude-main:{os.path.basename(facts.get('cwd', '?'))}"
    if rule.startswith(('system', 'core', 'tmux')):
        return 'system' if rule.startswith('system') else f'core:{short_name(proc["command"])}'
    if rule.startswith(('K4', 'proxy')):
        return 'proxy'
    return f'proc:{short_name(proc["command"])}'


def owner_of_session(session: str) -> str:
    if session.startswith(MONITOR_SESSION_PREFIX):
        return f'monitor:{session}'
    if session.startswith(WORKER_SESSION_PREFIX):
        return f'worker:{session}'
    return f'tmux:{session}'


def encoded_project(path: str) -> str:
    for base in (str(TASKS_BASE), '/private' + str(TASKS_BASE)):
        if path.startswith(base + '/'):
            return path[len(base) + 1:].split('/')[0]
    return '?'


def build_actions(rows: list) -> list:
    merged = {}
    for row in rows:
        action = row['action']
        if action is None:
            continue
        key = (action['kind'], action['target'])
        entry = merged.setdefault(key, {**action, 'rule': row['rule'], 'covers': [], 'cpu_now': 0.0, 'rss_mb': 0.0})
        entry['covers'].append(row['pid'])
        entry['cpu_now'] = round(entry['cpu_now'] + row['cpu_now'], 1)
        entry['rss_mb'] = round(entry['rss_mb'] + row['rss_mb'], 1)
    return sorted(merged.values(), key=lambda a: (-a['cpu_now'], -a['rss_mb']))


def summarize(snap: dict, rows: list) -> dict:
    return {
        'system': snap['system'],
        'process_total': len(rows),
        'counts': {g: sum(1 for r in rows if r['group'] == g) for g in GROUPS},
        'cpu_now': {g: round(sum(r['cpu_now'] for r in rows if r['group'] == g), 1) for g in GROUPS},
        'rss_mb': {g: round(sum(r['rss_mb'] for r in rows if r['group'] == g), 1) for g in GROUPS},
        'cpu_by_owner': cpu_by_owner_kind(rows),
        'hot_system': [r['pid'] for r in rows
                       if r['group'] == GROUP_ESSENTIAL and r['cpu_now'] >= REPORT_HOT_CPU_NOW_PERCENT
                       and r['rule'] in ('system_owner', 'system_path', 'tmux_server')],
    }


def cpu_by_owner_kind(rows: list) -> dict:
    totals = {}
    for r in rows:
        kind = r['owner'].split(':')[0]
        totals[kind] = round(totals.get(kind, 0.0) + r['cpu_now'], 1)
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))
