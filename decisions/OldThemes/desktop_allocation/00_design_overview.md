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

**Aktuelle (post-Probe) Mapping-Strategie:**

Phase A des Probe-Workers entdeckte dass AppleScript `bounds of (window of terminal)` für Ghostty NICHT existiert (`-1728` Error). Stattdessen funktioniert: AppleScript `id of terminal of tab of window` liefert UUID per Tab, und `kCGWindowName` der CGWindow korrespondiert zu Ghostty's `name`-Property des Window (= aktiver Tab-Titel).

**Drei-Strategie-Resolver** (in dieser Reihenfolge):
1. **Name-unique**: `kCGWindowName` = window_name in genau einem CGWindow → Hit
2. **Space-elimination**: bei mehreren Kandidaten, query `CGSCopySpacesForWindows` pro Kandidat, eliminiere die auf bereits-claimed Spaces (progressive Akkumulation in Worker-Iteration) → falls einer übrig → Hit
3. **OSC-2 Injection**: Marker `__DET_<hex>` per OSC-2 in den tty injecten, 150ms warten, `kCGWindowName` neu matchen → effektiv wenn CC-Tab der focused Tab im Window ist

**Detection-Rate empirisch:** 100% in beiden Probe-Runs (4/4, 3/3). Reference-Implementation: `dev/desktop_detection/01_probe.py`. Cross-Project Production-Variante: `Meta/blank/src/desktop/desktop_targeting.py`.

**Negativ-Befund von Bedeutung:** AppleScript `working directory of terminal` returnt für ALLE Ghostty-Terminals den App-Launch-Pfad (Monitor_CC) statt der echten Terminal-cwd — ein Ghostty-Bug. Erklärt rückwirkend warum das Menubar `_focus_session()` Path-B-Fallback (`focus first terminal whose working directory is "..."`) strukturell broken war. Fix dafür landed in commit `1725bfb` (proc_cwd preference + Path B MISS detection).

## Etappen

1. **Etappe 1 — Detection-Probe** (`dev/desktop_detection/01_probe.py`, commit `fee6566`): ✅ DONE. 100% Detection-Erfolg, proven. Cwd-Drift-Bug aufgedeckt + gefixt in `1725bfb`. Phase A/B Log in `A1_detection_probe.md`.
2. **Etappe 2 — Menubar-Display Desktop-Nr**: PENDING. SessionInfo bekommt `desktop_no` Feld, `panel.py` zeigt es als `[N]` Prefix. Konflikt-Detection (2 Mains auf einem Desktop) → Error-Marker. Hängt strukturell von Etappe 1 ab, jetzt unblocked.
3. **Etappe 3 — Worker-Placement auf Caller-Desktop** (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer`, commit `cfd0d14`): ✅ DONE. Nach osascript-Window-Spawn wird `python3 desktop_targeting.py wait-and-move "$PPID" "Ghostty" 5` im Hintergrund aufgerufen. Pending Live-Verifikation nach `plugin-publish`.
4. **Etappe 4 — File-Open-Placement** (`Meta/blank/bin/show`, commit `cfd0d14`): ✅ DONE. Identische Pattern: nach `open` Helper-Call mit `app_name` (CotEditor für md/txt, leer für andere → cross-app Polling). Siehe `file_open_routing.md` für Details. Pending Live-Verifikation nach `plugin-publish` (Helper liegt im selben Commit).

## Etappe 2 — Phase B Implementation (2026-05-28)

### Files changed

| File | Change |
|---|---|
| `src/menubar/desktop_detection.py` | NEW (275 LOC) — port of `dev/desktop_detection/01_probe.py` detection pipeline into importable library |
| `src/menubar/discover.py` | `SessionInfo.desktop_no: Optional[int] = None` added; `list_alive_sessions()` runs batch detection post-loop |
| `src/menubar/panel.py` | `_GRID_COL0_W` 33→40; `main_slot` counter removed; slot prefix driven by `desktop_no`; conflict set pre-computed via `Counter`; `app._desktop_to_cwd` populated |
| `src/menubar/app.py` | `_desktop_to_cwd: dict = {}` in `__init__`; `_reregister_digit_hotkeys` uses `_desktop_to_cwd` instead of `_cwd_map` |
| `src/menubar/DOCS.md` | New module entry, LOC updates, import graph + state table |

### Architecture decisions vs Plan

- **Performance**: 10s TTL cache at module level; force-invalidated on cwd-set change; runs on main thread (same pattern as existing ghostty TTY probe). Detection blocked inside outer `try/except` — any error (AppleScript failure, CGS error, Ghostty down) logs once and returns all-None for the cache TTL period.
- **Conflict UX**: `[!N]` in `NSColor.systemRedColor()` for slot cell; star/name/dot remain orange. `_desktop_to_cwd` excludes conflicted desktops → no Cmd+N hotkey registered for them.
- **All-fail log**: `log_menubar('detection', f'all_failed n_mains=N reason=...')` fires only when ALL mains return None (3 possible reasons: `ghostty_not_running`, `all_no_match`, `error:<repr>`). Partial failures (some mains detected, some not) produce no log entry.
- **SessionInfo backward compat**: `desktop_no: Optional[int] = None` as final field with default — all existing `SessionInfo(name=..., ..., tmux_session_name=...)` call sites unchanged.

### Smoke test result

```
Mains found: 2
  desktop=3  name=Monitor_CC       cwd=.../Monitor_CC
  desktop=2  name=searxng          cwd=.../Meta/ClaudeCode/MCP/searxng
```

Detection successful, 100%, strategy-breakdown expected to be `name-unique:2` or `osc2-injection:1` depending on focused tab state.

## Status (2026-05-27)

- **Etappe 1**: ✅ Done + verifiziert (probe lief 2× sauber, 100% Erfolg)
- **Etappe 2**: ✅ Done — `desktop_detection.py` + `SessionInfo.desktop_no` + panel prefix + hotkey mapping, commit on branch `cwd-exit-fix`
- **Etappe 3 + 4**: code-complete in blank/ commit `cfd0d14`, pending `plugin-publish` + Live-Test
- **Cwd-Drift-Bug (Nebenstrang)**: ✅ Done + gemerged, pending User Live-Verify (Menubar-Restart + Cmd+2/3)

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
