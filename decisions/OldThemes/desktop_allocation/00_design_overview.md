# Desktop Allocation — Design Overview (2026-05-27)

## Vision

Drei User-Goals die alle auf einer gemeinsamen Detection-Foundation aufbauen — der Fähigkeit zu wissen auf welchem macOS Mission-Control-Space (Desktop) eine bestimmte CC-Main-Session lebt:

1. **Menubar-Display**: für jede Main-Session zeigt das Menubar die Desktop-Nummer auf der sie sitzt. Heute zeigt es arbiträre Slot-Nummern `[1]` `[2]` `[3]` `[4]`. Soll: `[N]` = User-sichtbare Desktop-Nummer N.
2. **Worker-Placement**: wenn eine Main-Session einen Worker spawned, soll das neue Ghostty-Window auf demselben Desktop landen wie die spawning Main.
3. **File-Open-Placement**: wenn die `show <file>` Tool von einer Main-Session aufgerufen wird, soll die geöffnete App auf demselben Desktop sein wie diese Main.

## Invarianten (user-confirmed)

- Nie 2 Main-Sessions im selben Projekt
- Nie 2 Main-Sessions auf demselben Desktop
- Konflikte (versehentlich 2 Mains auf einem Desktop) → Error-State im Menubar, kein Auto-Resolve
- User-Launch-Pattern für Mains: ausschließlich `./src/claude_proxy_start.sh --project <ROOT>`. PROJECT ist der kanonische Root.

## API-Foundation

Apple's private CoreGraphics-Services (CGS) APIs unter `SkyLight.framework`. Stabil seit 10.10+, produktiv genutzt von yabai/AeroSpace/Amethyst/alt-tab-macos/Ice und von Ghostty selbst (siehe Ghostty's interne `macos/Sources/Helpers/Private/CGS.swift`).

| API | Zweck |
|---|---|
| `CGSMainConnectionID() → Int32` | Connection-ID, einmalig zu cachen |
| `CGSGetActiveSpace(cid) → SpaceID` | aktuell fokussierter Space (Diagnostik) |
| `CGSCopySpacesForWindows(cid, mask, [windowID]) → CFArray<SpaceID>` | Spaces auf denen eine Window erscheint |
| `CGSCopyManagedDisplaySpaces(cid) → CFArray<CFDict>` | geordnete Space-Liste pro Display; Array-Index pro Display = User-sichtbare Desktop-Nummer (1-based) |
| `CGSMoveWindowsToManagedSpace(cid, [windowID], spaceID) → Void` | verschiebt Window zu Space (funktioniert nicht für Fullscreen-Windows) |

Python-Anbindung über `ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')` plus `ctypes.CDLL('/usr/lib/libobjc.A.dylib')` für CFArray/CFDict-Bridging via `objc_msgSend`. Pattern aus `drussell23/JARVIS:backend/vision/macos_space_detector.py` bewährt.

## Die Mapping-Lücke cwd → CGWindowID

Unser `src/menubar/ghostty.py` mappt cwd → Ghostty-internes Terminal-UUID via OSC-2-Title-Probe. Diese UUID ist NICHT die macOS CGWindowID die `CGSCopySpacesForWindows` benötigt.

**Pre-approved Mapping-Strategie** (aus Phase A des verstorbenen Worker `menubar-hotkey-log`):

**Primär**: AppleScript `bounds of (window 1 of (terminal id "<UUID>"))` liefert NSRect der Ghostty-Window. Dann `CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)` filtern auf `kCGWindowOwnerPID == ghostty_pid`, und Bounds matchen mit ±2px Toleranz pro Dimension. Hit → `kCGWindowNumber` = die gesuchte CGWindowID.

**Fallback**: OSC-2-Re-Injection mit Marker-Präfix `__DET_`, dann `CGWindowListCopyWindowInfo` Match via `kCGWindowName`. Bekannte Limitation: reflektiert nur den aktiven Tab pro Ghostty-Fenster (Background-Tabs würden hier nicht matchen, sind aber via Primär abgedeckt).

**Ausgeschlossen**: Korrelation via `kCGWindowNumber` (no semantic link), AXUIElement (zu fragiles Permission-Setup).

## Etappen

1. **Etappe 1 — Detection-Probe** (`dev/desktop_detection/01_probe.py`): proves die Pipeline `cwd → Ghostty-UUID → CGWindowID → SpaceID → Desktop-Nr` funktioniert. Read-only, kein src/-Touch. Output: Tabelle pro Main + Spaces-per-Display-Diagnostik + Mismatch-Block. Status: Worker dispatched, Predecessor starb mit "Prompt is too long" mid-implementation (zero commits), Successor wird mit pre-approved Plan gespawnt.
2. **Etappe 2 — Menubar-Display**: SessionInfo bekommt `desktop_no` Feld, `panel.py` zeigt es als `[N]` Prefix. Konflikt-Detection (2 Mains auf einem Desktop) → roter Marker am Slot-Number. Hängt von Etappe 1 erfolgreich.
3. **Etappe 3 — Worker-Placement**: Hook in `iterative-dev` Plugin (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer()`) der nach Ghostty-Window-Spawn die neue CGWindowID identifiziert und auf den Desktop der spawning-Main via `CGSMoveWindowsToManagedSpace` schiebt. Touches Plugin-Source.
4. **Etappe 4 — File-Open-Placement**: integriert mit `file_open_routing` (separate OldTheme). Nach `open <file>` polling auf neue Window, dann move zum Ziel-Desktop.

## Status (2026-05-27)

- **Etappe 1**: in flight — Successor-Worker wird gerade gespawnt
- **Etappe 2-4**: pending Etappe 1 Verifikation

## Anhang — Worker-Death Notiz

Worker `menubar-hotkey-log` wurde nach Phase 5 Recap des Hotkey-Logging-Tasks weitergenutzt für Desktop-Detection (AGGRESSIVE-REUSE, thematische Kontinuität mit ghostty.py/menubar). Bei 22% Context Phase A clean abgeliefert, Go gegeben, Worker starb in Phase B Implementation mit "Prompt is too long" Error bevor irgendwas committed war. Successor erbt:

- Vor-approved Phase A Plan (in dieser Datei oben + im Successor-Prompt)
- Zero commits — also keine Handoff-Resume sondern frischer Spawn mit pre-approved Plan
- Folder `decisions/OldThemes/desktop_allocation/` existiert bereits, `A1_detection_probe.md` wird vom Successor in Phase B angelegt

## Quellen

- `src/menubar/ghostty.py` (existierendes UUID-Mapping)
- `src/menubar/discover.py:list_alive_sessions`
- `src/menubar/proc_cache.py:_cc_proc_cache`
- `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/ghostty_cwd_uuid.json` (Live cwd→UUID Map vom Menubar geschrieben)
- External: yabai source, alt-tab-macos `src/experimentations/PrivateApis.swift`, Ghostty's eigene `macos/Sources/Helpers/Private/CGS.swift`, JARVIS `backend/vision/macos_space_detector.py` (Python-ctypes-Pattern)
