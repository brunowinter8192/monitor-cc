# INFRASTRUCTURE
import os
import subprocess
import sys
import time
from pathlib import Path

_LABEL           = 'com.brunowinter.monitor_cc_menubar'
_PLIST_TMPL      = Path(__file__).resolve().parent / f'{_LABEL}.plist'
_LAUNCH_AGENTS   = Path.home() / 'Library' / 'LaunchAgents'
_DEST            = _LAUNCH_AGENTS / f'{_LABEL}.plist'
_PROJECT_ROOT    = Path(__file__).resolve().parent.parent.parent
_GUI_TARGET      = f'gui/{os.getuid()}/{_LABEL}'
_BUNDLE          = Path.home() / 'Applications' / 'Monitor_CC_Menubar.app'
_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'Monitor_CC_Menubar'

# ORCHESTRATOR

# Build .app bundle + codesign, write plist, bootout + bootstrap launchd service
def setup_menubar_workflow() -> None:
    _build_app_bundle()
    _codesign_bundle()
    write_plist()
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

# Read template, substitute tokens, write to ~/Library/LaunchAgents/
def write_plist() -> None:
    content = _PLIST_TMPL.read_text(encoding='utf-8')
    content = content.replace('<PROJECT_ROOT>', str(_PROJECT_ROOT))
    content = content.replace('<BUNDLE_LAUNCHER>', str(_BUNDLE_LAUNCHER))
    _LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    _DEST.write_text(content, encoding='utf-8')
    print(f'  wrote {_DEST}')

# Write Info.plist into bundle Contents/
def _write_info_plist(contents: Path) -> None:
    plist = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
        '  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '  <key>CFBundleIdentifier</key>\n'
        f'  <string>{_LABEL}</string>\n'
        '  <key>CFBundleName</key>\n'
        '  <string>Monitor_CC_Menubar</string>\n'
        '  <key>CFBundleExecutable</key>\n'
        '  <string>menubar</string>\n'
        '  <key>CFBundleVersion</key>\n'
        '  <string>1.0</string>\n'
        '  <key>CFBundleShortVersionString</key>\n'
        '  <string>1.0</string>\n'
        '  <key>CFBundlePackageType</key>\n'
        '  <string>APPL</string>\n'
        '  <key>LSUIElement</key>\n'
        '  <true/>\n'
        '  <key>LSMinimumSystemVersion</key>\n'
        '  <string>10.15</string>\n'
        '</dict>\n'
        '</plist>\n'
    )
    (contents / 'Info.plist').write_text(plist, encoding='utf-8')
    print(f'  wrote {contents / "Info.plist"}')

# Write bash launcher into bundle Contents/MacOS/ and chmod 755
def _write_launcher(macos: Path) -> None:
    script = (
        '#!/bin/bash\n'
        f'exec "{_PROJECT_ROOT}/venv/bin/python3" \\\n'
        f'     "{_PROJECT_ROOT}/workflow.py" \\\n'
        '     --mode menubar\n'
    )
    launcher = macos / 'menubar'
    launcher.write_text(script, encoding='utf-8')
    launcher.chmod(0o755)
    print(f'  wrote {launcher}')

# Create ~/Applications/Monitor_CC_Menubar.app bundle (always rebuild — overwrite-safe)
def _build_app_bundle() -> None:
    contents = _BUNDLE / 'Contents'
    macos    = contents / 'MacOS'
    macos.mkdir(parents=True, exist_ok=True)
    _write_info_plist(contents)
    _write_launcher(macos)
    print(f'  bundle: {_BUNDLE}')

# Ad-hoc codesign bundle so TCC tracks CFBundleIdentifier
def _codesign_bundle() -> None:
    r = subprocess.run(
        ['codesign', '-s', '-', '--deep', '--force', str(_BUNDLE)],
        capture_output=True, timeout=30)
    if r.returncode == 0:
        print(f'  codesign: ok')
    else:
        err = r.stderr.decode(errors='replace').strip()
        print(f'  codesign WARN (rc={r.returncode}): {err}', file=sys.stderr)

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
