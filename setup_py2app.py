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
# Verify:
#   codesign --verify --verbose=4 dist/monitor-cc-menubar.app
#   defaults read dist/monitor-cc-menubar.app/Contents/Info.plist CFBundleIdentifier
#   file dist/monitor-cc-menubar.app/Contents/MacOS/monitor-cc-menubar
#
# Does NOT install to ~/Applications/ — user copies manually after review.

import shutil
import sys
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

    # session_finder + constants are outside src.menubar (imported via ..)
    # so packages=['src.menubar'] alone won't pull them in.
    'includes': ['src.session_finder', 'src.constants'],

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
        # Required for osascript queries against Ghostty window list
        'NSAppleEventsUsageDescription': (
            "monitor-cc queries Ghostty's window list via AppleScript to identify "
            'Claude Code sessions.'
        ),
    },
}


# Whitelist: every src.X the menubar imports directly or transitively outside src.menubar.
# discover.py: from ..session_finder → session_finder.py
# session_finder.py: from .constants → constants.py
# NO other cross-package src imports exist (verified via grep).
_BUNDLE_SRC_KEEP = {'menubar', 'session_finder.py', 'constants.py', '__init__.py', '__pycache__'}


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


setup(
    name='monitor-cc-menubar',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

if 'py2app' in sys.argv:
    _prune_bundle_bloat()
