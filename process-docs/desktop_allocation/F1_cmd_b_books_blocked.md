# F1 — Cmd+B "Books auf aktuellen Desktop" — BLOCKED (Sackgasse)

**Datum:** 2026-05-29 · **Status:** Zurückgestellt, blockiert durch tote Move-API · **Tracking-Bead Monitor_CC-e2it geschlossen.**

## Feature-Absicht

Globaler Carbon-Hotkey Cmd+B, der die macOS Books-App auf den aktuell aktiven Desktop des Users holt — egal wo Books gerade lebt. Nicht nur Foreground: wenn Books-Fenster auf Desktop 1 liegen und der User auf Desktop 2 Cmd+B drückt, sollen die Books auf Desktop 2 erscheinen.

## Geplante Implementierung (NICHT gebaut)

- `src/menubar/hotkey.py`: `register_cmd_b()` analog zu `register_cmd_k` (Carbon-Pattern)
- `src/menubar/app.py`: Init-Hook für Registration + Callback-Wiring
- Neues Modul `src/menubar/desktop_actions.py` (~80 LOC): `CGSGetActiveSpace` → `CGWindowList` filter `kCGWindowOwnerName==Books` → `CGSMoveWindowsToManagedSpace` zu active_space → `osascript activate Books`

## Blocker — warum Sackgasse

Der Plan steht und fällt mit `CGSMoveWindowsToManagedSpace` (Fenster auf den aktiven Space schieben). Diese API ist auf **macOS 15.7 tot** — empirisch nachgewiesen 2026-05-29 (Probe + unabhängige Screenshot-/on-screen-Verifikation). Der Bead nahm an, das einzige Risiko sei TCC (`kCGWindowOwnerName` braucht kein Screen-Recording) — aber das eigentliche Problem ist die API selbst, nicht die Berechtigung. Cmd+B würde Books aktivieren, das Fenster bliebe aber auf seinem alten Desktop.

**Vollständige Sackgassen-Doku** (alle vier Move-APIs FAIL, yabai-Bridged-Op-Dispatcher fehlt auf 15.7, kein nicht-SIP-Weg): `Meta/blank/decisions/OldThemes/desktop_targeting_sidecar.md`.

## Verworfene Auswege (User-Entscheidung 2026-05-29)

- `activate` ohne Move = User wird auf Books' Desktop gesprungen → abgelehnt (Umschalten unerwünscht)
- Dock-Scripting-Addition + SIP-Teilabschaltung (yabai-Weg) → abgelehnt (kein Sicherheits-Trade-off)

## Wiederaufnahme

Gemeinsam mit dem übrigen Desktop-Move-Thema, sobald die Reddit-/gh-cli-Recherchewerkzeuge ausgereifter sind → Neu-Recherche zu macOS-15-Space-Placement. Bis dahin nicht bauen — sonst baut ein Worker denselben toten Pfad nach.

## Architektur-Schuld (falls je gebaut)

CGS-Bridging läge dann in drei Stellen: `src/menubar/desktop_detection.py`, `src/menubar/desktop_actions.py`, `Meta/blank/src/desktop/desktop_targeting.py`. Cleanup-Idee: gemeinsames Helper-Modul oder Monitor_CC src/ als Single-Source-of-Truth, blank/ shellt dorthin.
