# INFRASTRUCTURE
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# ORCHESTRATOR


def main():
    result = subprocess.run([sys.executable, '-m', 'src.ccwrap', '--project'], cwd=_ROOT, capture_output=True, text=True)
    ok = result.returncode == 2 and '--project requires a value' in result.stderr
    print(('PASS: ' if ok else 'FAIL: ') + '--project without a value exits 2 with a message')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
