# INFRASTRUCTURE
from sysload.collect import parse_tmux_sessions, run_text

_USAGE = 'usage: confirm pid <pid> <lstart> | confirm session <name> <created>'


# ORCHESTRATOR

def confirm_workflow(argv: list) -> int:
    kind, target, stamp = parse_confirm_args(argv)
    matches = check_target(kind, target, stamp)
    return report_verdict(matches)


# FUNCTIONS

def parse_confirm_args(argv: list) -> tuple:
    if len(argv) != 3 or argv[0] not in ('pid', 'session'):
        raise SystemExit(_USAGE)
    return argv[0], argv[1], argv[2]


def check_target(kind: str, target: str, stamp: str) -> bool:
    if kind == 'pid':
        return pid_matches(target, stamp)
    return session_matches(target, stamp)


def pid_matches(pid: str, lstart: str) -> bool:
    if not pid.isdigit():
        return False
    text = run_text(['ps', '-p', pid, '-o', 'lstart='])
    return text is not None and bool(text.strip()) and ' '.join(text.split()) == ' '.join(lstart.split())


def session_matches(name: str, created: str) -> bool:
    text = run_text(['tmux', 'list-sessions', '-F', '#{session_name}|#{session_created}'])
    if text is None:
        return False
    return any(s['name'] == name and str(s['created']) == created for s in parse_tmux_sessions(text))


def report_verdict(matches: bool) -> int:
    print('ok' if matches else 'changed')
    return 0 if matches else 1
