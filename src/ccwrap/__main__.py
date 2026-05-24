# INFRASTRUCTURE

import sys
from pathlib import Path

from .wrapper import run, _DEFAULT_PROJECT, _SCRIPT_REL, _LOG_DIR

# ORCHESTRATOR


# Parse argv, build the shell command, invoke the PTY wrapper
def main() -> None:
    args = sys.argv[1:]
    project = _DEFAULT_PROJECT
    passthrough: list = []

    i = 0
    while i < len(args):
        if args[i] == '--project' and i + 1 < len(args):
            project = args[i + 1]
            i += 2
        else:
            passthrough.append(args[i])
            i += 1

    script = str(Path(project) / _SCRIPT_REL)
    cmd = ['bash', script, '--project', project] + passthrough
    sys.exit(run(cmd, _LOG_DIR))


main()
