# A2 — Restart-Button Fix (2026-05-28)

**Status:** Fixed. Commits 089980c + 2a7acd8 on branch `restart-fix`.

## Root Cause (zwei zusammenwirkende Bugs)

### Bug 1 — `_BUNDLE_LAUNCHER` zeigt auf nicht-existentes Binary

`setup_menubar.py:_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'menubar'`

`write_plist()` substituiert diesen Pfad in `ProgramArguments` der LaunchAgent-Plist.
Das installierte py2app-Bundle enthält aber kein `Contents/MacOS/menubar`:

```
~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/
  Monitor_CC_Menubar   ← py2app native Mach-O
  python               ← py2app Stub-Python
```

Verifiziert via `launchctl print gui/<uid>/com.brunowinter.monitor_cc_menubar`:
- `program = .../Contents/MacOS/menubar`
- `active count = 0`, `state = spawn scheduled`

launchd versuchte respawnen; Binary existiert nicht; App lief nur weil manuell via `open` gestartet.

### Bug 2 — Helper-Subprocess korrumpiert Info.plist des py2app-Bundles

`restartApp_` baute den Helper-Command:
```python
cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
```

Im py2app-Bundle-Kontext:
- `sys.executable` = `Contents/MacOS/python` (Bundle-internes Stub-Python)
- `_SETUP_PY` = `Contents/Resources/lib/python3.14/src/menubar/setup_menubar.py` (Bundle-interne Kopie, verifiziert via `find`)

Der Helper rief `setup_menubar_workflow()` → `_build_app_bundle()` auf, das:
1. `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` mit dem ad-hoc-Stub überschrieb
   (`CFBundleExecutable=menubar`, kein `PyRuntimeLocations`, kein `NSScreenCaptureUsageDescription`)
2. `Contents/MacOS/menubar` (Bash-Launcher) anlegte — neben dem py2app-Native-Binary

Nächster `open`-Versuch: py2app-Native-Binary liest korrupte Info.plist →
"The Info.plist file must have a PyRuntimeLocations array" (fataler Startfehler).

Severity schärfer als in A1 antizipiert: nicht nur "no-op exit" sondern aktive Bundle-Korruption.

## Fix (Option D — separate Plist-Funktionen, sys.frozen-Gate)

### Schritt 1: `setup_menubar.py` — `_BUNDLE_EXE` + `write_plist_py2app()`

```python
_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'menubar'           # dev/Bash-Bundle unverändert
_BUNDLE_EXE      = _BUNDLE / 'Contents' / 'MacOS' / 'Monitor_CC_Menubar'  # py2app native binary
```

Neue Funktion `write_plist_py2app()` — identisch zu `write_plist()` aber substituiert `_BUNDLE_EXE`
statt `_BUNDLE_LAUNCHER`. Kein `print()` (kein nützlicher stdout-Empfänger im Bundle-Kontext).
`_BUNDLE_LAUNCHER` bleibt unverändert → `write_plist()` + dev-Restart weiterhin korrekt.

### Schritt 2: `app.py:restartApp_` — `sys.frozen`-Gate, kein unbedingter Wrong-Write

```python
def restartApp_(self, sender):
    uid = os.getuid()
    label = 'com.brunowinter.monitor_cc_menubar'
    if getattr(sys, 'frozen', False):
        # py2app: write_plist_py2app() → reiner launchctl-Cycle
        from .setup_menubar import write_plist_py2app
        write_plist_py2app()
        dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
        cmd = (
            f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
            f'launchctl bootstrap gui/{uid} "{dest}"'
        )
    else:
        # dev/venv: write_plist() → setup_menubar.py subprocess
        from .setup_menubar import write_plist
        write_plist()
        cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
    subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
    rumps.quit_application()
```

`sys.frozen = 'macosx_app'` wird von `__boot__.py` gesetzt — verifiziert.
Kein Python-Call im py2app-Helper → Bundle-interne `setup_menubar.py` kann nie anlaufen.

### Warum kein unbedingtes `write_plist()` am Anfang

Erster Entwurf (Commit 089980c) hatte `write_plist()` unbedingt oben, dann `write_plist_py2app()`
im py2app-Branch: redundanter Wrong-Write (`menubar`-Pfad, sofort überschrieben durch `Monitor_CC_Menubar`).
Commit 2a7acd8 korrigiert das: jeder Branch ruft genau eine, die richtige Funktion auf.

## Offener Footgun (nicht gefixxt — Refactor-Scope)

Dev-Restart (`sys.frozen = False`): `setup_menubar_workflow()` ruft `_build_app_bundle()` auf,
das `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` überschreibt — korrumpiert ein
installiertes py2app-Bundle. In der Praxis inaktiv: Dev läuft via `dev/menubar_debug.py`,
kein Restart-Button-Click aus diesem Pfad erwartet. Fix gehört in den `setup_menubar.py`-Refactor-Step
(Legacy-Pipeline entfernen oder Guard einbauen).

## Quellen

- `src/menubar/app.py:restartApp_` (Commits 089980c, 2a7acd8)
- `src/menubar/setup_menubar.py` (`_BUNDLE_EXE`, `write_plist_py2app`)
- `decisions/OldThemes/menubar_restart_broken/A1_observed_corruption.md`
- `decisions/menubar_desktop_allocation.md` § Offene Fragen #4
