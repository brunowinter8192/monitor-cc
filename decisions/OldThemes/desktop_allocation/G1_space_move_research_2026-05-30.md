# G1 — Space-Move Neu-Recherche: bridged-Op + macOS-Versions-Split (2026-05-30)

**Status:** Recherche abgeschlossen. Supersedet F1s „alle Move-APIs tot" teilweise — der bridged-Pfad lebt, aber versionsabhängig. Probe-First pending.

Knüpft an: `F1_cmd_b_books_blocked.md` (Move-API-Sackgasse), `Meta/blank/decisions/OldThemes/desktop_targeting_sidecar.md` (blank-Probe + Sackgassen-Protokoll der Vorsession).

## Frage

F1/Vorsession parkten den Space-Move als „Sackgasse, alle 4 Move-APIs failen, Wiederaufnahme via gh-Recherche". Diese Session hat die gründliche GitHub-Recherche gemacht (Issues + Discussions indexiert über yabai, Hammerspoon, DockDoor, AeroSpace).

## Root Cause (jetzt präzise belegt)

Move-Window-to-Space scheitert auf Sequoia 15.7 wegen **WindowServer-Connection-Rights-Checking**, das Apple in Sequoia eingeführt hat: der Aufrufer muss **Owner des Fensters** sein ODER **Dock.app** (= System-Verwalter aller Spaces; yabais Scripting-Addition injiziert dort hinein → braucht SIP). „Owner" = der Prozess, der das Fenster erzeugt hat (WindowServer vermerkt Owner-PID pro Fenster).

Unser Verschiebe-Helfer (`desktop_targeting.py`, eigener Python-Prozess) besitzt weder das Ghostty- noch das CotEditor-Fenster → auf Sequoia blockiert. Das ist der eigentliche Grund, nicht „API weg".

Quellen: Hammerspoon #3636 Kommentar 15 (spaces-Extension-Maintainer, wörtlich: *"rights checking on the WindowServer connection. You either need to be the owner of the window, or the system universal owner (Dock.app)"*); yabai-Discussion #803 (Maintainer: *"the entire workspaces functionality is implemented inside Dock.app"*); yabai-Issues #2380/#2425/#2500/#2784 (Move braucht SIP+SA seit Sequoia).

## Die fehlende Technik (warum unser Probe scheiterte)

Der korrekte Weg ist `SLSBridgedMoveWindowsToManagedSpaceOperation` + die **eigene Methode des Operation-Objekts `performWithWMBridgeDelegate`** — Referenz: `ejbills/DockDoor:DockDoor/Utilities/PrivateApis.swift` `func SLSMoveWindowsToManagedSpace`. Reine ObjC-Runtime (`NSClassFromString` + `initWithWindows:spaceID:` + `performWithWMBridgeDelegate`), kein Mach-O-Parsing.

Unser Vorsessions-Probe scheiterte an zwei Dingen:
1. Es rief `.start` direkt auf der Klasse → SIGSEGV (falscher Selektor).
2. Es suchte den externen Dispatcher `SLSPerformAsynchronousBridgedWindowManagementOperation` per `dlsym` → MISSING (lokales `_ZL`-Symbol, dlsym findet es nie; yabai resolved es per `macho_find_symbol`, DockDoor umgeht den Dispatcher ganz via `performWithWMBridgeDelegate`).

Der korrekte Selektor `performWithWMBridgeDelegate` wurde im Vorsessions-Probe NIE getestet.

## macOS-Versions-Split (der Kern)

| macOS | Move-to-Space (non-owned, SIP-frei) | Beleg |
|---|---|---|
| ≤ 14.4 | ✅ funktioniert | yabai #803, kasper/phoenix |
| 14.5 (Sonoma) | API geändert, dann ge-NOP't | Hammerspoon #3636 c24, phoenix PHSpace.m („only works prior to 14.5") |
| 15.x (Sequoia) | ❌ rights-gated (owner-or-Dock); same-display cross-space tot, nur cross-**Display** geht | yabai #2380/#2784 (15.7.5), DockDoor #855/#451/#953 (15.2/15.5) |
| 26.4.1 (Tahoe) | ✅ **bridged-Op SIP-frei** | yabai #2788 + DockDoor #855 c7 (ejbills validiert, „validated working on macOS 26.4.1"); yabai-Maintainer #2784 c3 (Move läuft auf seinem Tahoe-Daily-Driver) |

yabai = lebender Beweis, dass der bridged-Op auf Tahoe non-owned Fenster verschiebt (yabai managed fremde App-Fenster). Edge-Case (yabai #2789): Move auf einen **leeren** Space failt auf 26.4.1 — unser Ziel (Caller-Desktop) ist nie leer → unbetroffen.

## Verworfene SIP-freie Workarounds (alle disruptiv)

- Titelleiste greifen + Ctrl+Pfeil (nativer Shortcut, Hammerspoon #3636 jdtsmith-Hack, auf 15.0.1 bestätigt) — wechselt den Space.
- Mission-Control-Drag-Automation (`mogenson/Drag.spoon`) — reißt Mission Control auf.
- MC-Keyboard-Shortcuts via osascript/skhd (yabai #803) — wechselt den Space.

Alle verletzen „lautlos platzieren ohne den User zu stören".

## Referenz-Repos + Patterns

- `asmvik/yabai` — `src/space_manager.c:665-700` (3 Move-Pfade), `src/yabai.c:149` (macho-Symbol-Resolution für Dispatcher). Issues = Ground-Truth zum SIP/Versions-Status.
- `ejbills/DockDoor` — `DockDoor/Utilities/PrivateApis.swift` `SLSMoveWindowsToManagedSpace` (saubere Swift-Referenz via `performWithWMBridgeDelegate`). Issue #855 = Validierungs-Quelle.
- `Hammerspoon/hammerspoon` — #3698/#3636 (spaces-Extension-Status, owner-or-Dock-Erklärung).
- `nikitabobko/AeroSpace` — vermeidet native Spaces bewusst (Referenz falls „native Spaces aufgeben" je erwogen wird).

## SOLL / Nächster Schritt

**Entscheidung User 2026-05-30: Tahoe-Route, kein Sequoia-Tweaking.** Der Sequoia-Probe mit `performWithWMBridgeDelegate` wird NICHT gemacht — Sequoia ist rights-gated, Tahoe ist der einzige bestätigte SIP-freie Weg, Aufwand auf 15.7 lohnt nicht.

1. **Software-Update auf Tahoe 26.4+** (dort bridged-Op SIP-frei bestätigt: yabai #2788, ejbills/DockDoor #855 c7, yabai-Maintainer #2784).
2. Danach **dev/-Probe auf Tahoe**: real ein non-owned Fenster (Ghostty) auf einen Ziel-Space schieben via `SLSBridgedMoveWindowsToManagedSpaceOperation` + `performWithWMBridgeDelegate` (DockDoor `PrivateApis.swift` als Swift-Referenz). Verlässliche Messung: On-Screen-Liste (`CGWindowListCopyWindowInfo` kCGWindowListOptionOnScreenOnly) + Screenshot, NICHT `SLSCopySpacesForWindows`.
3. Probe grün → bridged-Op-Technik nach `Meta/blank/src/desktop/desktop_targeting.py` portieren. Probe-First (Worker-Rules §5): erst dev/, dann `src/`.

## Indexierte Quellen (RAG)

- `github_issues`: yabai (#2380/#2425/#2500/#2636/#2741/#2784/#2788/#2789/#2707/#2634), Hammerspoon (#3698/#3636/#3111/#2111), DockDoor (#855/#451/#953/#466/#9/#1177).
- `github_discussions`: yabai (#803/#1553/#2667), AeroSpace (native-spaces-Begründung).
