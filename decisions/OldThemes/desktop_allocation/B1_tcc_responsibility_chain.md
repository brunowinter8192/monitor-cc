# B1 — TCC Responsibility Chain Investigation (Etappe 2 Blocker)

**Status:** Etappe 2 (Menubar zeigt Desktop-Nr als [N] Slot-Prefix) ON ICE wegen unauflösbarem macOS TCC-Issue. Detection-Pipeline funktioniert perfekt — blockiert nur im launchd-spawned Menubar-Process. Etappe 1, 3, 4 unaffected (laufen aus User-Shell-Kontext).

## Symptom

Menubar im Live-Betrieb: `cgwindow_by_name` Dict aus `_cgwindow_list_ghostty()` ist immer leer. Granular-Logs zeigen `cgw_list_empty pid=1250 iterated=264 no_names_returned` — CGWindowListCopyWindowInfo iteriert 264 Windows, ZERO matchen die Ghostty-PID. Konsequenz: alle Mains kriegen `desktop_no=None`, kein `[N]` Prefix, Cmd+digit-Allocation fällt zurück auf arbiträre Slot-Logik (aber Hotkey-Registration findet nichts → keine Funktion).

Standalone-Test aus User-Shell mit identischem Python-Code: `cgwindow_by_name` enthält 3 Ghostty-Window-Names korrekt, Detection 100%.

## Root Cause

macOS TCC (Transparency, Consent, Control) gated `CGWindowListCopyWindowInfo` so dass Owner-PIDs für Windows ANDERER Apps NICHT exposed werden ohne Screen-Recording-Permission. Die Permission wird per **audit token** zur API-Call-Zeit gecheckt — die Audit Token enthält die Binary-Identity (Bundle-ID + Pfad + Code-Signature) des CURRENT-executing Process.

Im Menubar-Kontext: launchd → `~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/menubar` (Bash) → `exec` → `/opt/homebrew/.../Python.app/Contents/MacOS/Python` → Audit Token bei API-Call ist Python.app's Identity, NICHT unsere Bundle-Identity. `exec` replaced den Process — Bundle-Identity geht verloren.

Im User-Shell-Kontext: CC (Claude Code) hat eine eigene App-Identity mit Screen-Recording-Grant. CC spawnt Bash, Bash spawnt Python — Responsibility-Chain wurzelt bei CC, TCC-Lookup findet den Grant.

## Was wir versucht haben (alle gefailed)

| Versuch | Was | Ergebnis | Begründung |
|---|---|---|---|
| 1 | Screen-Recording an Homebrew `Python.app` im System Settings granten | Funktioniert in User-Shell-Kontext, NICHT im launchd-Kontext | TCC checkt nicht nur die Binary sondern auch den Responsibility-Parent — bei launchd kein User-Grant in der Kette |
| 2 | `CGSCopyWindowProperty` (private SkyLight-API) statt `kCGWindowName` aus CGWindowList | In Shell-Kontext: liefert Titel korrekt. In launchd: identische Failure-Rate | TCC-Gate sitzt nicht auf API-Ebene sondern auf Process-Visibility-Ebene — egal welche API, Owner-PID-Filter bringt 0 Treffer weil andere Apps' Windows komplett unsichtbar sind |
| 3 | Spinner-Glyph-Normalisierung (`✻` `⠂` `✳` Prefix strippen vor Window-Name-Match) | Orthogonaler Fix der echte Edge-Cases adressiert (race zwischen AppleScript-Read und CGS-Read), aber nicht TCC-blocker | Bleibt drin als Hardening |
| 4 | Menubar in eigene `.app` Bundle wrappen, ad-hoc codesignen, User grants Screen-Recording auf das Bundle | TCC-Listing registriert das Bundle, Toggle aktiviert, trotzdem nicht effektiv | Bash-Launcher im Bundle exec'd zu generic Python — Audit-Token bei CGWindowList-Call ist Python, nicht Bundle. Bundle-Identity geht beim `exec` verloren |
| 5 | Launch via `open -na` aus Finder-Kontext (statt launchd) | Identische Failure-Rate | Auch hier: Bundle-Launcher exec'd zu Python → Audit-Token = Python |

## Empirische Verifikation der Root-Cause

CGWindowList-Counts in den getesteten Kontexten:

| Launch-Kontext | Total Windows | Owned by Ghostty PID 1250 |
|---|---|---|
| User-Shell (CC-Bash subprocess) | 271 | 19 ✅ |
| launchd → Bundle-Wrapper → Python | 264 | 0 ❌ |
| Finder `open -na` → Bundle → Python | 271 | 0 ❌ |

Bestätigt: TCC-Filter applied **basierend auf Caller-Identity**, nicht auf API-Auswahl oder Launch-Method.

## Zukunfts-Pfade (für nächste Session)

Drei Optionen, vom kleinsten zum größten Refactor:

### A) py2app — Menubar als natives Bundle mit embedded Python

py2app bundlet Python + Code + dependencies in eine richtige `.app` Struktur. Resulting Binary ist ein nativer Mach-O Executable (kein generic Python-Wrapper). Audit Token bei API-Calls = unsere Bundle-Identity. User grants Screen-Recording → tatsächlich effektiv.

Aufwand: ~30-60 min Setup. py2app ist mature, gut dokumentiert. Bestehendes `~/Applications/Monitor_CC_Menubar.app` Bundle ist eine Foundation die nur den Launcher ersetzt bekommt.

### B) nuitka — Python zu nativem Binary kompilieren

Ähnlich py2app aber kompiliert tatsächlich. Resulting ist single Mach-O Executable mit unserer Identity. Mehr Compile-Zeit, etwas weniger Setup-Friction als py2app.

### C) Separate Helper-Process aus User-Shell-Kontext

Helper-Script läuft permanent aus User-Shell-Context (Auto-Start via `~/.zshrc` Hook oder Login Items). Schreibt Detection-Resultate alle 5s in JSON-File. Menubar (launchd) liest nur das File — kein direkter CGS-Call aus launchd-Kontext.

Vorteil: kein Bundle-Refactor. Nachteil: zusätzlicher Process der laufen muss, IPC via File.

## Aktueller Code-State (preserved für Refactor)

- `src/menubar/desktop_detection.py` (275 LOC): vollständige Detection-Pipeline, drei-Strategie-Resolver (name-unique → space-elimination → OSC-2), CGSCopyWindowProperty-bypass-attempt, Spinner-Normalize. **Funktioniert im Shell-Kontext** (Etappe 3+4 nutzen das transparent via `Meta/blank/src/desktop/desktop_targeting.py`).
- `src/menubar/setup_menubar.py`: erweitert um `_build_app_bundle()` + `_codesign_bundle()`. Bundle-Build ist idempotent — Re-Run überschreibt sauber. Foundation für py2app-Refactor.
- `~/Applications/Monitor_CC_Menubar.app/`: ad-hoc signed Bundle mit `com.brunowinter.monitor_cc_menubar` Identity. Bash-Launcher in `Contents/MacOS/menubar`. Stub für py2app — bei dem Refactor wird der Bash-Launcher durch native Mach-O ersetzt.
- LaunchAgent-Plist: ProgramArguments zeigt auf Bundle-Launcher, nicht mehr direkt auf python. Bundle wrapped die TCC-Identity sauber up für späteren Refactor.
- Granular Diagnostic-Logs in `_cgwindow_list_ghostty` / `_cgwindow_title` / `_resolve_cgwindow_id`: bleiben drin — beim nächsten Session-Start helfen sie sofort zu verifizieren ob ein Refactor TCC funktional gemacht hat.

## Was JETZT noch funktioniert

- **Etappe 1**: Probe `dev/desktop_detection/01_probe.py` läuft aus Shell-Kontext, 100% Erfolg. Verifiziert dass die Detection-Logik korrekt ist.
- **Etappe 3**: Worker-Spawn (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer`) ruft `desktop_targeting.py wait-and-move` aus CC-Bash-Kontext auf. TCC-Vererbung von CC → funktioniert.
- **Etappe 4**: `show <file>` (`Meta/blank/bin/show`) ruft `desktop_targeting.py wait-and-move` aus CC-Bash-Kontext auf. Identisch funktional.
- **Hotkey-Logging, Cwd-Drift-Fix, Main-Exit-Detection** (alle separaten Bug-Fixes von dieser Session): vollständig funktional, unabhängig von TCC.

## Was JETZT NICHT funktioniert

- **Etappe 2 — Menubar zeigt Desktop-Nr `[N]` Prefix für Mains**: alle desktop_no=None, Slot-Spalte bleibt leer. Cmd+digit-Allocation greift nicht. User-Experience: Mains werden gezeigt aber ohne Slot-Nummer, Cmd+1..9 macht nix.

## Quellen

- `src/menubar/desktop_detection.py` (Detection-Pipeline, Diagnostic-Logs)
- `src/menubar/setup_menubar.py` (Bundle-Build-Pipeline)
- `~/Applications/Monitor_CC_Menubar.app/` (Bundle-Stub)
- `dev/desktop_detection/01_probe.py` (Detection-Probe, Shell-Kontext-Validation)
- `Meta/blank/src/desktop/desktop_targeting.py` (Helper für Etappe 3+4)
- `src/logs/menubar.log` — `[detection]` category enthält Live-Diagnostics aus dem aktuellen Run
- External: `lwouis/alt-tab-macos:src/macos/api-wrappers/CGWindowID.swift` (CGSCopyWindowProperty Pattern), `ejbills/DockDoor:DockDoor/Utilities/PrivateApis.swift` (SkyLight private APIs reference)
