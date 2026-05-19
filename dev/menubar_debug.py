# INFRASTRUCTURE
import argparse
import os
import subprocess
import sys
from pathlib import Path

_LABEL       = 'com.brunowinter.monitor_cc_menubar'
_GUI_TARGET  = f'gui/{os.getuid()}/{_LABEL}'
_PLIST       = Path.home() / 'Library' / 'LaunchAgents' / f'{_LABEL}.plist'
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW    = _PROJECT_ROOT / 'workflow.py'
_PYTHON      = _PROJECT_ROOT / 'venv' / 'bin' / 'python3'

# ORCHESTRATOR

# Bootout launchd service, run menubar in foreground with diagnostics enabled; re-bootstrap on exit
def menubar_debug_workflow(rebootstrap: bool) -> None:
    _bootout()
    print(f'Starting {_LABEL} in foreground (MENUBAR_DIAGNOSTICS=1) ...')
    print('Press Ctrl-C to stop.\n')
    env = {**os.environ, 'MENUBAR_DIAGNOSTICS': '1'}
    try:
        subprocess.run([str(_PYTHON), str(_WORKFLOW), '--mode', 'menubar'],
                       env=env, cwd=str(_PROJECT_ROOT))
    except KeyboardInterrupt:
        print('\nStopped.')
    if rebootstrap:
        _bootstrap()

# FUNCTIONS

# launchctl bootout — print result, ignore failure
def _bootout() -> None:
    r = subprocess.run(['launchctl', 'bootout', _GUI_TARGET],
                       capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f'bootout {_LABEL}: ok')
    else:
        print(f'bootout {_LABEL}: not loaded (ok)')

# launchctl bootstrap from installed plist
def _bootstrap() -> None:
    if not _PLIST.exists():
        print(f'WARNING: {_PLIST} not found — run src/menubar/setup_menubar.py first.')
        return
    r = subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(_PLIST)],
                       capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f'bootstrap {_LABEL}: ok')
    else:
        print(f'bootstrap failed (rc={r.returncode}): {r.stderr.decode(errors="replace").strip()}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run menubar app in foreground with diagnostics.')
    parser.add_argument('--rebootstrap', action='store_true',
                        help='Re-register launchd service after stopping')
    args = parser.parse_args()
    menubar_debug_workflow(args.rebootstrap)
