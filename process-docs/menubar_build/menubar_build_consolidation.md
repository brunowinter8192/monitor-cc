# Menubar-Build konsolidiert — ein kanonischer py2app-Install (2026-06-12)

## Ausgangs-Verwirrung

Es gab ZWEI Build-Wege für die Menubar, was beim Deploy zu einem laufenden **python-Prozess**
statt einer compilierten Binary führte:

- `setup_py2app.py` (project root) — echter py2app-Compile → native Mach-O, eingebettetes Python.
  Der KANONISCHE Weg (DOCS: "replaces the Bash-exec chain").
- `src/menubar/setup_menubar.py` — LEGACY: dünner Bash-Launcher, der `workflow.py` per python startet
  (`exec venv/python workflow.py --mode menubar`). DOCS: "superseded by setup_py2app.py".

Beim Deploy wurde versehentlich der Legacy-Weg gefahren → `.app` = Bash-Launcher → python-Prozess
(statt self-contained Binary). Das war die "Verwirrung".

## Footgun (Historie in menubar_restart_broken/)

`app.py:restartApp_` Dev-Branch rief `python setup_menubar.py` → `setup_menubar_workflow()` →
`_build_app_bundle()` → überschrieb die Info.plist eines installierten py2app-Bundles → Korruption.

## Install-Orchestrierungs-Lücke (beim Refactor entdeckt)

`setup_menubar_workflow()` machte build + codesign + write_plist + bootout + bootstrap in EINEM.
Das reine Entfernen der Legacy-Pipeline hätte die Install-Orchestrierung (plist + bootstrap)
heimatlos gemacht — `setup_py2app.py` baute nur (`dist/`), installierte nicht (DOCS: "user copies
manually"). Diese Lücke wurde im Refactor geschlossen (siehe Entscheidung 3).

## Entscheidung

1. **`setup_menubar.py` → reines Plist-Helper-Modul** (143 → 30 LOC): nur die 8 Konstanten +
   `write_plist()`/`write_plist_py2app()` (von `restartApp_` gebraucht). Legacy-Build-Pipeline
   (`setup_menubar_workflow`, `_build_app_bundle`, `_write_launcher`, `_codesign_bundle`, `_bootout`,
   `_bootstrap`, `__main__`-Guard) entfernt.
2. **Footgun entschärft**: Dev-Restart-Branch in `restartApp_` nutzt jetzt denselben reinen
   launchctl-Cycle wie der py2app-Branch — kein Bundle-Rebuild aus `setup_menubar.py` mehr möglich.
3. **`setup_py2app.py` zum EINEN vollständigen Install gemacht**: nach dem Build läuft `_install_bundle()`
   (post-setup-Hook neben `_prune_bundle_bloat`) → rmtree+copytree nach `~/Applications`, ad-hoc
   codesign, plist inline (natives Binary), launchctl bootout+bootstrap **mit Retry** (der erste
   bootstrap scheitert empirisch mit rc=5 I/O-Error, Retry nach 1 s greift). plist-Logik inline statt
   `import` (Import von `src.menubar.setup_menubar` würde im Build-Kontext den AppKit-schweren
   Menubar-Code laden).
4. **`dev/menubar_debug.py`** Warnung auf `./venv/bin/python setup_py2app.py py2app` korrigiert.

## Endstand

Ein Befehl `./venv/bin/python setup_py2app.py py2app` macht **build + install + bootstrap**.
Menubar läuft als native Mach-O-Binary (51 MB, gültig signiert, `codesign --verify` clean),
kein python-Prozess mehr. Das `codesign WARN (rc=1)` beim Install ist nur die Info-Zeile
"replacing existing signature" — Signatur ist gültig.

## Quellen
- Commits auf dev: `37ce26c` (refactor), `437d09e` (install), `b9d1465` (bootstrap-retry), `af5ac48` (docs)
- `decisions/OldThemes/menubar_restart_broken/` (Footgun-Historie)
- `src/menubar/DOCS.md` (`setup_menubar.py` + `setup_py2app.py` Einträge)
