# INFRASTRUCTURE
import sys

from sysload.cli import cli_workflow

if __name__ == '__main__':
    sys.exit(cli_workflow(sys.argv[1:]))
