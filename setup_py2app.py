# INFRASTRUCTURE
# py2app build script for monitor-cc-menubar.app
#
# MUST be run from project root (here) — NOT from src/menubar/.
# Reason: Python adds the script's directory to sys.path[0]; if run from src/menubar/,
# setuptools' internal `import queue` would find src/menubar/queue.py instead of stdlib.
#
# Usage:
#   ./venv/bin/pip install py2app   # one-time
#   ./venv/bin/python setup_py2app.py py2app
#
# Output: dist/monitor-cc-menubar.app/  (semi_standalone=False → embedded Python.framework ~80MB)
# After build: installs to ~/Applications/, writes launchd plist, bootstraps service.
# Verify:
#   codesign --verify --verbose=4 dist/monitor-cc-menubar.app
#   defaults read dist/monitor-cc-menubar.app/Contents/Info.plist CFBundleIdentifier
#   file dist/monitor-cc-menubar.app/Contents/MacOS/monitor-cc-menubar

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from setuptools import setup

_PYTHON_VER = f'{sys.version_info.major}.{sys.version_info.minor}'

APP = ['src/menubar/menubar_main.py']

# plist template is read by setup_menubar.py at runtime via Path(__file__).parent
# Place it alongside setup_menubar.py inside the bundle's lib tree
DATA_FILES = [
    (f'lib/python{_PYTHON_VER}/src/menubar',
     ['src/menubar/com.brunowinter.monitor-cc-menubar.plist']),
]

OPTIONS = {
    # No argv_emulation — we don't need macOS Open Document events mapped to sys.argv
    'argv_emulation': False,

    # semi_standalone=False: embed full Python.framework (~80MB) → completely self-contained;
    # no dependency on system Python or Homebrew surviving/changing.
    'semi_standalone': False,

    # src.menubar: force-include the whole subpackage — lazy imports inside
    # system.run() and restartApp_ won't be traced by modulegraph otherwise.
    # rumps: explicit inclusion guards against modulegraph missing it via transitive paths.
    'packages': ['src.menubar', 'rumps'],

    # session_finder + colors + constants + tmux_launcher + monitor_janitor are outside
    # src.menubar (imported via ..) — 'packages': ['src.menubar'] copies that whole subpackage's
    # source wholesale without running modulegraph's import scanner over its contents (that's WHY
    # it needs 'packages' at all — see the comment above), so nothing imported from inside it is
    # auto-discovered; each cross-package target needs its own explicit include.
    # colors: session_finder.py's own colors (2026-09, constants-split milestone — session_finder
    # moved from `from .constants import RESET, ...` to `from .colors import RESET, ...`).
    # constants: still needed independently — tmux_launcher.py itself imports TMUX_HISTORY_LIMIT
    # from constants.py, unaffected by the split.
    # tmux_launcher: system.py's per-project monitor button (generate_session_name,
    # check_session_exists). monitor_janitor: monitor_sweep_scheduler.py's daily tmux sweep.
    'includes': ['src.session_finder', 'src.colors', 'src.constants', 'src.tmux_launcher', 'src.monitor_janitor'],

    # Exclude heavy non-menubar packages present in the venv.
    # modulegraph won't trace them from our entry chain, but belt-and-suspenders.
    'excludes': [
        'mitmproxy', 'flask', 'tornado', 'httpx', 'httpcore',
        'aioquic', 'werkzeug', 'jinja2', 'cryptography', 'brotli',
        'urwid', 'mitmproxy_rs',
    ],

    # Info.plist keys — CFBundleIdentifier MUST match existing TCC grant
    'plist': {
        'CFBundleIdentifier':       'com.brunowinter.monitor-cc-menubar',
        'CFBundleName':             'monitor-cc-menubar',
        'CFBundleVersion':          '1.0',
        'CFBundleShortVersionString': '1.0',
        'CFBundlePackageType':      'APPL',
        # Pure menubar app — no Dock icon, no app switcher entry
        'LSUIElement':              True,
        'LSMinimumSystemVersion':   '10.15',
        # Required for CGWindowListCopyWindowInfo + kCGWindowName visibility
        'NSScreenCaptureUsageDescription': (
            'Monitor_CC reads Ghostty window titles to map Claude Code sessions '
            'to Mission Control desktops. No screen content is captured or stored.'
        ),
        # Required for osascript queries against Ghostty window list
        'NSAppleEventsUsageDescription': (
            "monitor-cc queries Ghostty's window list via AppleScript to identify "
            'Claude Code sessions.'
        ),
    },
}


# Whitelist: every src.X the menubar imports directly or transitively outside src.menubar.
# discover.py: from ..session_finder → session_finder.py
# session_finder.py: from .colors → colors.py (2026-09, constants-split milestone — was
#   `from .constants import RESET, ...`; constants.py itself is STILL needed below, independently,
#   because tmux_launcher.py imports TMUX_HISTORY_LIMIT from it, unaffected by the split)
# system.py: from ..tmux_launcher → tmux_launcher.py
# tmux_launcher.py: from .constants → constants.py
# monitor_sweep_scheduler.py: from ..monitor_janitor → monitor_janitor.py
# monitor_janitor.py: from .tmux_launcher → tmux_launcher.py (already kept above)
# Checked whether any other menubar-transitive import now touches a constants-split destination
# module (pane_error_log.py, core/modes.py): NO — menubar's only cross-package import outside
# this chain is discover.py's session_finder.py; pane_error_log.py and core/ are never imported
# by anything menubar reaches, transitively or otherwise (grep-confirmed).
# Independent of OPTIONS['includes'] above — this prunes by name regardless of how a file
# landed under the bundle's src/, so a module missing here gets deleted post-build even if
# modulegraph did trace it.
_BUNDLE_SRC_KEEP = {'menubar', 'session_finder.py', 'colors.py', 'constants.py', 'tmux_launcher.py',
                    'monitor_janitor.py', '__init__.py', '__pycache__'}


# Prune the bundle's src/ to whitelist only — prevents copy_package_data() from
# copying src/logs/ (15 GB runtime proxy logs, no __init__.py → swept wholesale by py2app).
def _prune_bundle_bloat() -> None:
    src_lib = (Path('dist/monitor-cc-menubar.app/Contents/Resources')
               / f'lib/python{_PYTHON_VER}/src')
    if not src_lib.exists():
        return
    removed = []
    for entry in src_lib.iterdir():
        if entry.name not in _BUNDLE_SRC_KEEP:
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
            removed.append(entry.name)
    if removed:
        print(f'  pruned from bundle src/: {", ".join(sorted(removed))}')


# Detect a stable-identity cert in the keychain — no -v: self-signed roots report
# CSSMERR_TP_NOT_TRUSTED and get filtered out by -v, so the check would false-negative.
def _find_signing_identity(name: str) -> bool:
    r = subprocess.run(['security', 'find-identity', '-p', 'codesigning'],
                       capture_output=True, timeout=10)
    return name in r.stdout.decode(errors='replace')


# Copy dist/ bundle to ~/Applications, codesign, write launchd plist, bootout+bootstrap service
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
        print(f'  codesign WARN (rc={r.returncode}): {r.stderr.decode(errors="replace").strip()}')
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


setup(
    name='monitor-cc-menubar',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

if 'py2app' in sys.argv:
    _prune_bundle_bloat()
    _install_bundle()
