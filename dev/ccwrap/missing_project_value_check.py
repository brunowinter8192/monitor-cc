# INFRASTRUCTURE
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


# ORCHESTRATOR

def main():
    result = subprocess.run([sys.executable, '-m', 'src.ccwrap', '--project'], cwd=_ROOT, capture_output=True, text=True)
    ok = compute_ok(result)
    print_project_without_a(ok)
    exit_with_status(ok)


# FUNCTIONS

def compute_ok(result):
    return result.returncode == 2 and '--project requires a value' in result.stderr


def print_project_without_a(ok):
    print(('PASS: ' if ok else 'FAIL: ') + '--project without a value exits 2 with a message')


def exit_with_status(ok):
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
