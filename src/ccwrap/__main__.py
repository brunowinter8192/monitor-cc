# INFRASTRUCTURE
import sys
from pathlib import Path

from src.ccwrap.wrapper import run, _DEFAULT_PROJECT, _SCRIPT_REL, _LOG_DIR

# ORCHESTRATOR

def main() -> None:
    project, passthrough = _parse_argv()
    cmd = _build_command(project, passthrough)
    sys.exit(run(cmd, _LOG_DIR))

# FUNCTIONS

def _parse_argv() -> tuple:
    args = sys.argv[1:]
    project = _DEFAULT_PROJECT
    passthrough: list = []
    i = 0
    while i < len(args):
        if args[i] == '--project':
            if i + 1 >= len(args):
                print('--project requires a value', file=sys.stderr)
                sys.exit(2)
            project = args[i + 1]
            i += 2
        else:
            passthrough.append(args[i])
            i += 1
    return project, passthrough

def _build_command(project: str, passthrough: list) -> list:
    script = str(Path(project) / _SCRIPT_REL)
    return ['bash', script, '--project', project] + passthrough

if __name__ == '__main__':
    main()
