# INFRASTRUCTURE
# py2app build script for Monitor_CC_Menubar.app
#
# MUST be run from project root (here) — NOT from src/menubar/.
# Reason: Python adds the script's directory to sys.path[0]; if run from src/menubar/,
# setuptools' internal `import queue` would find src/menubar/queue.py instead of stdlib.
#
# Usage:
#   ./venv/bin/pip install py2app   # one-time
#   ./venv/bin/python setup_py2app.py py2app
#
# Output: dist/Monitor_CC_Menubar.app/  (semi_standalone=False → embedded Python.framework ~80MB)
# Verify:
#   codesign --verify --verbose=4 dist/Monitor_CC_Menubar.app
#   defaults read dist/Monitor_CC_Menubar.app/Contents/Info.plist CFBundleIdentifier
#   file dist/Monitor_CC_Menubar.app/Contents/MacOS/Monitor_CC_Menubar
#
# Does NOT install to ~/Applications/ — user copies manually after review.

import sys
from setuptools import setup

_PYTHON_VER = f'{sys.version_info.major}.{sys.version_info.minor}'

APP = ['src/menubar/menubar_main.py']

# plist template is read by setup_menubar.py at runtime via Path(__file__).parent
# Place it alongside setup_menubar.py inside the bundle's lib tree
DATA_FILES = [
    (f'lib/python{_PYTHON_VER}/src/menubar',
     ['src/menubar/com.brunowinter.monitor_cc_menubar.plist']),
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
        'CFBundleIdentifier':       'com.brunowinter.monitor_cc_menubar',
        'CFBundleName':             'Monitor_CC_Menubar',
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
            "Monitor_CC queries Ghostty's window list via AppleScript to identify "
            'Claude Code sessions.'
        ),
    },
}

setup(
    name='Monitor_CC_Menubar',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
