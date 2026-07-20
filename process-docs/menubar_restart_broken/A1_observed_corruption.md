# A1 — Menubar Restart-Button korrumpiert Bundle (2026-05-28)

**Status:** Observation. Reproducible. Severity: blockt jeden Restart-Button-Klick + verlangt manuellen Rebuild + neue Screen-Recording-Permission.

## Beobachtung

Klick auf "Restart" Button im Menubar-Panel (Modal mit Kill / Restart Buttons) führt nicht zu einem sauberen Re-Launch des py2app-Bundles. Stattdessen:

1. Menubar exited (richtig)
2. Bundle wird AKTIV korrumpiert — Info.plist wird mit ad-hoc-stub-Version überschrieben (`CFBundleExecutable=menubar` statt `Monitor_CC_Menubar`, keine `NSScreenCaptureUsageDescription`, kein `PyRuntimeLocations`)
3. Bash-Launcher `Contents/MacOS/menubar` (243 Bytes) wird zusätzlich angelegt — neben dem py2app-native Binary das schon dort liegt
4. Nächster Launch-Versuch via `open` schlägt fehl mit System-Dialog: *"Monitor_CC_Menubar has encountered a fatal error... The Info.plist file must have a PyRuntimeLocations array..."*

Bundle ist im Zustand "mixed Frankenstein": py2app-Binary + Bash-Launcher + ad-hoc-stub-plist, gleichzeitig.

## Root Cause

`src/menubar/app.py:restartApp_` invokes:

```python
cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
```

wobei `_SETUP_PY = Path(__file__).resolve().parent / 'setup_menubar.py'`. Im py2app-Bundle-Kontext:
- `sys.executable` = bundle-internes Python (`Contents/MacOS/python`)
- `_SETUP_PY` = bundle-internes `setup_menubar.py` (`Contents/Resources/lib/python3.14/src/menubar/setup_menubar.py`)

`setup_menubar.py:_build_app_bundle()` schreibt `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` neu (mit der alten ad-hoc-Stub-Konfiguration aus dem Template `com.brunowinter.monitor_cc_menubar.plist`) und legt den Bash-Launcher an. Der Plist-Write OVERWRITES die py2app-Konfiguration die das Bundle laufend benötigt.

Das war im IST-Dokument `decisions/menubar_desktop_allocation.md` § Offene Fragen #4 als "Restart button exits the app but does not re-bootstrap" antizipiert. Heute manifestiert sich das als AKTIVE Korruption, nicht nur als "no-op exit" — schärfere Severity als ursprünglich dokumentiert.

## Workaround (current)

Nach Restart-Click muss manuell:
1. Bundle aus `dist/` neu kopieren ODER `./venv/bin/python setup_py2app.py py2app` rebuild
2. `cp -R dist/Monitor_CC_Menubar.app ~/Applications/Monitor_CC_Menubar.app` (oder `rm -rf` first)
3. `open ~/Applications/Monitor_CC_Menubar.app`
4. Screen Recording Permission re-binden (neue CDHASH wenn rebuild)

## Fix-Optionen (zu entscheiden bei Implementation)

**Option A — restartApp_ in py2app-Kontext disable:**
- Detection via `getattr(sys, 'frozen', False)` oder `os.environ.get('RESOURCEPATH')` (py2app setzt diese)
- Im Bundle: Restart-Button wird zu reinem Quit-Button, oder zeigt Dialog "Restart not available in bundled mode"
- Vorteil: keine Korruption, klare UX
- Nachteil: Restart-Funktionalität nicht mehr verfügbar

**Option B — restartApp_ ruft py2app-konformen Rebuild:**
- Statt `setup_menubar.py` → call `subprocess.Popen` der den externen `~/Applications/Monitor_CC_Menubar.app` mit `open` neu launched, nachdem das aktuelle Process exited
- Setup_menubar.py wird NICHT mehr getriggert — keine Plist-Korruption
- Vorteil: Restart funktioniert wieder
- Nachteil: braucht `open` als External-Trigger + cleanen Exit-Sequenz

**Option C — setup_menubar.py löschen / als no-op markieren:**
- Datei aus src/menubar/ entfernen, Funktionalität in setup_py2app.py konsolidieren
- restartApp_ darauf anpassen
- Vorteil: keine Doppel-Pipeline mehr (siehe DOCS-Notiz "setup_menubar.py superseded by setup_py2app.py")
- Nachteil: größerer Code-Eingriff

## Quellen

- `Monitor_CC-docs: decisions/menubar_desktop_allocation.md` § Offene Fragen #4 (originale Antizipation)
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/C1_py2app_migration.md` (py2app-Bundle-Pipeline)
- `src/menubar/app.py:restartApp_`
- `src/menubar/setup_menubar.py:_build_app_bundle`
- Beobachtung 2026-05-28 19:27: Bundle nach Restart-Click hatte `CFBundleExecutable=menubar` + missing PyRuntimeLocations
