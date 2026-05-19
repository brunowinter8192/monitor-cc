# INFRASTRUCTURE
import os
import subprocess
import sys
import time
from pathlib import Path

_LABEL        = 'com.brunowinter.monitor_cc_menubar'
_PLIST_TMPL   = Path(__file__).resolve().parent / f'{_LABEL}.plist'
_LAUNCH_AGENTS = Path.home() / 'Library' / 'LaunchAgents'
_DEST         = _LAUNCH_AGENTS / f'{_LABEL}.plist'
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GUI_TARGET   = f'gui/{os.getuid()}/{_LABEL}'

# ORCHESTRATOR

# Substitute PROJECT_ROOT, write plist to LaunchAgents, bootout + bootstrap launchd service
def setup_menubar_workflow() -> None:
    _write_plist()
    _bootout()
    ok = _bootstrap()
    if not ok:
        print('  retry in 1s...')
        time.sleep(1)
        ok = _bootstrap()
    if ok:
        print(f'Done. {_LABEL} running via launchd.')
    else:
        print(f'ERROR: bootstrap failed twice. Check /tmp/monitor_cc_menubar.err', file=sys.stderr)
        sys.exit(1)

# FUNCTIONS

# Read template, substitute <PROJECT_ROOT>, write to ~/Library/LaunchAgents/
def _write_plist() -> None:
    content = _PLIST_TMPL.read_text(encoding='utf-8')
    content = content.replace('<PROJECT_ROOT>', str(_PROJECT_ROOT))
    _LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    _DEST.write_text(content, encoding='utf-8')
    print(f'  wrote {_DEST}')

# launchctl bootout — ignore failure (service may not be loaded)
def _bootout() -> None:
    r = subprocess.run(
        ['launchctl', 'bootout', _GUI_TARGET],
        capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f'  bootout {_LABEL}: ok')
    else:
        print(f'  bootout {_LABEL}: not loaded (ok)')

# launchctl bootstrap — returns True on success
def _bootstrap() -> bool:
    r = subprocess.run(
        ['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(_DEST)],
        capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f'  bootstrap {_LABEL}: ok')
        return True
    stderr = r.stderr.decode(errors='replace').strip()
    print(f'  bootstrap failed (rc={r.returncode}): {stderr}')
    return False


if __name__ == '__main__':
    setup_menubar_workflow()
