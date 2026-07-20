# cmd+N — Ghostty kommt auf allen Schreibtischen nach vorn (RESOLVED 2026-06-12)

## Symptom

Ein Session-Wechsel über die Menubar-Hotkeys (cmd+1..9) bzw. Panel-Klick holte Ghostty auf
JEDEM Schreibtisch in den Vordergrund, statt nur das eine Ziel-Terminal auf seinem Space.
Erwartet: Switch auf den Ziel-Space + nur dort Ghostty vorn.

## Ursache

`_focus_session(cwd)` (`src/menubar/system.py`) baute AppleScript
`tell application "Ghostty" → activate → focus terminal id "<UUID>"`.
Das `activate` ist das Cocoa-**App-level** `NSApplication.activate` → macht Ghostty zur
globalen Vordergrund-App → Ghosttys Fenster floaten auf JEDEM Space nach vorn.

## Evidenz (Ghostty sdef + Live-A/B-Test)

Ghostty Scripting Dictionary (`/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`, v1.3.1):
- `focus` command: *"Focus a terminal, **bringing its window to the front**"* — window-level.
- `activate window` command: window-level Activate (existiert; wurde nicht gebraucht).
- Das app-level `activate` im Code ist NICHT Ghosttys Befehl, sondern Cocoa-Standard.

Live-A/B-Test auf der User-Maschine (2026-06-12):
- `focus terminal id "<UUID>"` OHNE `activate` → nur das EINE Ziel-Fenster kam nach vorn
  (User: "nur das fragliche").
- Funktioniert auch wenn eine ANDERE App (CotEditor) vorn ist → Ghostty kommt drüber.
- Fazit: das `activate` ist reiner Schaden; `focus` allein reicht und schaltet auf den Space.

## Fix

`src/menubar/system.py:_focus_session` — die `activate`-Zeile aus BEIDEN AppleScript-Strings
(Path A UUID + Path B cwd-match) entfernt, sonst nichts. Auf dev gemergt, dann in die compilierte
py2app-Menubar eingebacken (siehe `menubar_build_consolidation.md`).

**Live verifiziert** (2026-06-12, compilierte Menubar): cmd+N holt nur das Ziel-Terminal vor,
andere Schreibtische bleiben unberührt.

## Quellen
- `src/menubar/system.py:_focus_session`
- `/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef` (v1.3.1)
- Commit auf dev: `c29fec8` (merge des `_focus_session`-Fix)
