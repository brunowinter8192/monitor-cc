# Comment salvage for setup_py2app.py — 2026-09-24

Build script of the menubar bundle (py2app options, bundle pruning, signing, launchd install). Salvage per the rule that every comment is relocated verbatim before deletion; no triage.

Every comment removed from `setup_py2app.py`, verbatim, grouped by consecutive comment block in source order. Line numbers refer to the file before removal. Each block names the code line that followed it. The three section markers stay in the file and are not listed. The file contains no docstring and nothing reads `__doc__`.

## Salvage from setup_py2app.py

### Lines 2-17, followed by `import os`

```
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
```

### Lines 31-32, followed by `DATA_FILES = [`

```
# plist template is read by setup_menubar.py at runtime via Path(__file__).parent
# Place it alongside setup_menubar.py inside the bundle's lib tree
```

### Lines 39-39, followed by `'argv_emulation': False,`

```
    # No argv_emulation — we don't need macOS Open Document events mapped to sys.argv
```

### Lines 42-43, followed by `'semi_standalone': False,`

```
    # semi_standalone=False: embed full Python.framework (~80MB) → completely self-contained;
    # no dependency on system Python or Homebrew surviving/changing.
```

### Lines 46-48, followed by `'packages': ['src.menubar', 'rumps'],`

```
    # src.menubar: force-include the whole subpackage — lazy imports inside
    # system.run() and restartApp_ won't be traced by modulegraph otherwise.
    # rumps: explicit inclusion guards against modulegraph missing it via transitive paths.
```

### Lines 51-61, followed by `'includes': ['src.session_finder', 'src.colors', 'src.constants', 'src.tmux_launcher', 'src.monitor_janitor'],`

```
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
```

### Lines 64-65, followed by `'excludes': [`

```
    # Exclude heavy non-menubar packages present in the venv.
    # modulegraph won't trace them from our entry chain, but belt-and-suspenders.
```

### Lines 72-72, followed by `'plist': {`

```
    # Info.plist keys — CFBundleIdentifier MUST match existing TCC grant
```

### Lines 79-79, followed by `'LSUIElement':              True,`

```
        # Pure menubar app — no Dock icon, no app switcher entry
```

### Lines 82-82, followed by `'NSScreenCaptureUsageDescription': (`

```
        # Required for CGWindowListCopyWindowInfo + kCGWindowName visibility
```

### Lines 87-87, followed by `'NSAppleEventsUsageDescription': (`

```
        # Required for osascript queries against Ghostty window list
```

### Lines 96-111, followed by `_BUNDLE_SRC_KEEP = {'menubar', 'session_finder.py', 'colors.py', 'constants.py', 'tmux_launcher.py',`

```
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
```

### Lines 116-117, followed by `def _prune_bundle_bloat() -> None:`

```
# Prune the bundle's src/ to whitelist only — prevents copy_package_data() from
# copying src/logs/ (15 GB runtime proxy logs, no __init__.py → swept wholesale by py2app).
```

### Lines 132-133, followed by `def _find_signing_identity(name: str) -> bool:`

```
# Detect a stable-identity cert in the keychain — no -v: self-signed roots report
# CSSMERR_TP_NOT_TRUSTED and get filtered out by -v, so the check would false-negative.
```

### Lines 140-140, followed by `def _install_bundle() -> None:`

```
# Copy dist/ bundle to ~/Applications, codesign, write launchd plist, bootout+bootstrap service
```

## Process notes

- Removed: 62 full-line comments. Kept: the `# INFRASTRUCTURE` marker. No docstring existed and a grep for `__doc__` in the file returned nothing.
- Verification: the file was NOT executed, because running it builds the bundle, installs it to `~/Applications` and bootstraps a launchd service. Instead the token sequence was compared before and after with comments and NL tokens dropped: 961 tokens on both sides, identical.
- Blank lines inside the `OPTIONS` dict were dropped together with the comments that separated its entries.
- The module has no ORCHESTRATOR or FUNCTIONS marker although it runs several steps at module level (`setup(...)`, prune, install). That structure was out of scope for the comment removal and was left unchanged.
