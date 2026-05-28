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
2. **Etappe 2 — Menubar-Display Desktop-Nr**: ⏸ ON ICE (2026-05-28). Code-complete in commit-chain `15c0319` → `5507c89` → `a719139` → `19986b9` → `3f0f0c7` (Spinner-normalize + CGSCopyWindowProperty + .app-Bundle-Wrapper). Detection-Pipeline architectural sauber implementiert und funktional bewiesen — aber TCC-Restriction für launchd-spawned Python verhindert dass die Menubar Owner-PIDs für Ghostty-Windows sieht. Volle Investigation + Future-Refactor-Pfade in `B1_tcc_responsibility_chain.md`. Nächste Session: py2app oder nuitka Refactor.
3. **Etappe 3 — Worker-Placement auf Caller-Desktop** (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer`, commit `cfd0d14`): ✅ DONE. Nach osascript-Window-Spawn wird `python3 desktop_targeting.py wait-and-move "$PPID" "Ghostty" 5` im Hintergrund aufgerufen. Funktional verifiziert — TCC unbetroffen weil Helper aus CC-Bash-Subprocess-Kontext läuft (Screen-Recording von CC vererbt via Responsibility-Chain).
4. **Etappe 4 — File-Open-Placement** (`Meta/blank/bin/show`, commit `cfd0d14`): ✅ DONE. Identische Pattern: nach `open` Helper-Call mit `app_name` (CotEditor für md/txt, leer für andere → cross-app Polling). Siehe `file_open_routing.md` für Details. Funktional verifiziert via Helper-Aufruf aus CC-Kontext. Caveat: aus Terminal.app ohne Screen-Recording würde auch dort failen — User-spezifischer Use-Case betrifft das nicht.

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

## Status (2026-05-28 — Session End)

- **Etappe 1** ✅: Detection-Probe `dev/desktop_detection/01_probe.py` — 100% Erfolg im Shell-Kontext, proven
- **Etappe 2** ⏸ ON ICE: Code-complete, aber TCC-Restriction blockiert Detection im launchd-spawned Menubar-Process. User-Grant für die `Monitor_CC_Menubar.app` Bundle aktiviert, trotzdem blockiert — root cause empirisch identifiziert: `exec` von Bash-Launcher zu Python verliert Bundle-Identity (Audit Token bei API-Call ist Python.app, nicht unser Bundle). Volle Investigation + drei Refactor-Pfade (py2app / nuitka / shell-helper) dokumentiert in `B1_tcc_responsibility_chain.md`. **Resume next session via Bead.**
- **Etappe 3** ✅: Worker-Spawn-Placement — verifiziert dass Helper aus CC-Bash-Subprocess space_id korrekt detektiert (TCC-Inheritance von CC funktional)
- **Etappe 4** ✅: show-File-Open-Placement — identische Pattern, gleich verifiziert
- **Cwd-Drift-Bug**: ✅ Done — Mains zeigen Project-Root-Name (nicht mehr drift via JSONL-cwd), Cmd+digit-Focus funktional
- **Hotkey-Logging**: ✅ Done — alle Carbon-Hotkeys loggen nach `src/logs/menubar.log`
- **Main-Exit-Detection**: ✅ Done — exited Mains verschwinden binnen ~1.5s aus Panel (statt 1h JSONL-Stale-Wait)
- **TCC-Identity-Architecture**: Bundle-Wrapper unter `~/Applications/Monitor_CC_Menubar.app` ad-hoc-signed; launchd-plist auf Bundle-Launcher umgestellt. Foundation für py2app-Refactor, kostet im aktuellen State nichts (menubar läuft genau wie vorher).

### TCC-Investigation Zusammenfassung (warum Etappe 2 stuck ist)

Sequenz der Fix-Attempts und warum jeder gefailed:
1. Screen-Recording-Grant für Homebrew `Python.app` → User-Shell-Kontext funktional, launchd-Kontext nicht (Responsibility-Chain wurzelt bei launchd ohne Grant)
2. `CGSCopyWindowProperty` private SkyLight-API statt `kCGWindowName` → identisches Failure-Pattern (TCC-Gate ist nicht API-bound sondern Process-Visibility-bound)
3. Spinner-Glyph-Normalisierung → orthogonaler Fix der bleibt; löst nicht TCC sondern Title-Matching-Edge-Case
4. `.app` Bundle wrap mit ad-hoc Codesign → Bundle-Identity korrekt registriert in TCC, User grant ON → **trotzdem blockiert**, weil Bash-Launcher exec'd zu Python und Audit-Token nach exec = Python.app

**Root cause final:** TCC-Audit-Token wird per Process zur API-Call-Zeit ermittelt. `exec` replaced den Process — Bundle-Identity geht verloren. Nur native-Mach-O-Bundle (py2app oder nuitka) löst das sauber.

**Helper-Process-Alternative**: separater Detection-Helper aus User-Shell-Kontext (Auto-Start via Login Items) der per JSON-File mit Menubar IPC'd — wäre Workaround ohne Refactor. Aufwand vs py2app vergleichbar. Beide Optionen offen für nächste Session.

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
