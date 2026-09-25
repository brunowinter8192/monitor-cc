# INFRASTRUCTURE
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from setuptools import setup

_PYTHON_VER = f'{sys.version_info.major}.{sys.version_info.minor}'

APP = ['src/menubar/menubar_main.py']

DATA_FILES = [
    (f'lib/python{_PYTHON_VER}/src/menubar',
     ['src/menubar/com.brunowinter.monitor-cc-menubar.plist']),
]

OPTIONS = {
    'argv_emulation': False,
    'semi_standalone': False,
    'packages': ['src.menubar', 'rumps'],
    'includes': ['src.session_finder', 'src.colors', 'src.constants', 'src.tmux_launcher', 'src.monitor_janitor', 'src.monitor_root'],
    'excludes': [
        'mitmproxy', 'flask', 'tornado', 'httpx', 'httpcore',
        'aioquic', 'werkzeug', 'jinja2', 'cryptography', 'brotli',
        'urwid', 'mitmproxy_rs',
    ],
    'plist': {
        'CFBundleIdentifier':       'com.brunowinter.monitor-cc-menubar',
        'CFBundleName':             'monitor-cc-menubar',
        'CFBundleVersion':          '1.0',
        'CFBundleShortVersionString': '1.0',
        'CFBundlePackageType':      'APPL',
        'LSUIElement':              True,
        'LSMinimumSystemVersion':   '10.15',
        'NSScreenCaptureUsageDescription': (
            'Monitor_CC reads Ghostty window titles to map Claude Code sessions '
            'to Mission Control desktops. No screen content is captured or stored.'
        ),
        'NSAppleEventsUsageDescription': (
            "monitor-cc queries Ghostty's window list via AppleScript to identify "
            'Claude Code sessions.'
        ),
    },
}


_BUNDLE_SRC_KEEP = {'menubar', 'session_finder.py', 'colors.py', 'constants.py', 'tmux_launcher.py',
                    'monitor_janitor.py', 'monitor_root.py', '__init__.py', '__pycache__'}

# ORCHESTRATOR

def setup_workflow() -> None:
    _run_setup()
    if 'py2app' in sys.argv:
        _prune_bundle_bloat()
        _install_bundle()

# FUNCTIONS

def _run_setup() -> None:
    setup(
        name='monitor-cc-menubar',
        app=APP,
        data_files=DATA_FILES,
        options={'py2app': OPTIONS},
        setup_requires=['py2app'],
    )

def _prune_bundle_bloat() -> None:
    src_lib = (Path('dist/monitor-cc-menubar.app/Contents/Resources')
               / f'lib/python{_PYTHON_VER}/src')
    if not src_lib.exists():
        print(f'  prune failed: bundle src lib missing: {src_lib}')
        sys.exit(1)
    removed = []
    for entry in src_lib.iterdir():
        if entry.name not in _BUNDLE_SRC_KEEP:
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
            removed.append(entry.name)
    if removed:
        print(f'  pruned from bundle src/: {", ".join(sorted(removed))}')

def _install_bundle() -> None:
    label  = 'com.brunowinter.monitor-cc-menubar'
    dist   = Path('dist/monitor-cc-menubar.app')
    dst    = Path.home() / 'Applications' / 'monitor-cc-menubar.app'
    tmpl   = Path('src/menubar/com.brunowinter.monitor-cc-menubar.plist')
    agents = Path.home() / 'Library' / 'LaunchAgents'
    plist  = agents / f'{label}.plist'
    exe    = dst / 'Contents' / 'MacOS' / 'monitor-cc-menubar'
    root   = Path(__file__).resolve().parent
    uid    = os.getuid()
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(dist, dst, symlinks=True)
    print(f'  installed: {dst}')
    identity = 'monitor-cc Code Signing'
    if _find_signing_identity(identity):
        cmd = ['codesign', '--sign', identity, '--force', '--deep', str(dst)]
        status = f'signed-with: {identity} (TCC grant survives rebuilds)'
    else:
        cmd = ['codesign', '-s', '-', '--deep', '--force', str(dst)]
        status = 'signed-with: ad-hoc (Screen Recording grant will reset on rebuild)'
        print('  WARNING: no signing identity found — TCC grant will reset on rebuild')
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    if r.returncode == 0:
        print('  codesign: ok')
    else:
        print(f'  codesign failed (rc={r.returncode}): {r.stderr.decode(errors="replace").strip()}')
        sys.exit(1)
    print(f'  {status}')
    content = tmpl.read_text(encoding='utf-8')
    content = content.replace('<PROJECT_ROOT>', str(root))
    content = content.replace('<BUNDLE_LAUNCHER>', str(exe))
    agents.mkdir(parents=True, exist_ok=True)
    plist.write_text(content, encoding='utf-8')
    print(f'  plist: {plist}')
    subprocess.run(['launchctl', 'bootout', f'gui/{uid}/{label}'],
                   capture_output=True, timeout=10)
    r = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(plist)],
                       capture_output=True, timeout=10)
    if r.returncode != 0:
        print(f'  bootstrap retry in 1s (rc={r.returncode})...')
        time.sleep(1)
        r = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(plist)],
                           capture_output=True, timeout=10)
    if r.returncode == 0:
        print(f'  bootstrap {label}: ok')
    else:
        print(f'  bootstrap failed (rc={r.returncode}): {r.stderr.decode(errors="replace").strip()}')
        sys.exit(1)

def _find_signing_identity(name: str) -> bool:
    r = subprocess.run(['security', 'find-identity', '-p', 'codesigning'],
                       capture_output=True, timeout=10)
    return name in r.stdout.decode(errors='replace')

if __name__ == '__main__':
    setup_workflow()
