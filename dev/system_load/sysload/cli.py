# INFRASTRUCTURE
import sys

from sysload.confirm import confirm_workflow
from sysload.diff import diff_workflow
from sysload.snapshot import snapshot_workflow

_USAGE = 'usage: sysload snapshot [--protect-pid N] [--protect-root PATH] [--out FILE] [--json] | confirm ... | diff BEFORE AFTER'


# ORCHESTRATOR

def cli_workflow(argv: list) -> int:
    command, rest = split_command(argv)
    if command == 'snapshot':
        return snapshot_workflow(rest)
    if command == 'confirm':
        return confirm_workflow(rest)
    if command == 'diff':
        return diff_workflow(rest)
    return fail_usage()


# FUNCTIONS

def split_command(argv: list) -> tuple:
    if not argv:
        return '', []
    return argv[0], argv[1:]


def fail_usage() -> int:
    print(_USAGE, file=sys.stderr)
    return 2
