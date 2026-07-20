# H1 — Placement-Mechanismus Review + Redesign-Richtung (2026-05-31)

**Status:** ABGESCHLOSSEN (2026-05-31). Move SIP-frei zwischen nativen Spaces auf 26.5 bewiesen unmöglich (G4: 5/5 Move-APIs no-op MIT vollen AX+SC-Rechten; ökosystemweit bestätigt). Dead-Code-Rollback ausgeführt (Monitor_CC menubar + Meta/iterative-dev-Plugin). Siehe `## Abschluss` unten. Knüpft an G1 (Recherche), G2 (bridged-op Probe → FAIL), G3 (Detection-Probe → gelöst), G4 (Move-Sweep → alle FAIL).

## Auslöser

Nach Tahoe-Update (macOS 26.5, Build 25F71) bridged-Op getestet → FAIL (G2). User-Beobachtung beim Worker-Spawn: neues Fenster landete "auf Main-Space" → Verdacht "geht doch / wir machen irgendwo was falsch, Versions-Blame ist inkohärent". Session = Produktions-Mechanismus auseinandergenommen + zwei vermengte Threads getrennt.

## Zwei getrennte Threads (vorher von Opus vermengt)

### Thread A — bridged-Op auf Tahoe

- **Prämisse G1:** bridged-Op (`SLSBridgedMoveWindowsToManagedSpaceOperation` → `initWithWindows:spaceID:` → objekt-eigene `performWithWMBridgeDelegate`) ist SIP-frei, extern validiert auf **26.4.1**: ejbills DockDoor #855 c7 wörtlich *"validated working on macOS 26.4.1"*; yabai #2788; yabai-Maintainer #2784 (läuft auf seinem Tahoe-Daily-Driver).
- **G2 (diese Session):** Technik korrekt getestet — richtige Klasse, korrektes `initWithWindows:spaceID:` (NSArray von NSNumber<UInt32>), korrektes `performWithWMBridgeDelegate`. Ergebnis: **stiller No-op auf 26.5**. Objekt erzeugt (kein nil), Call ohne Crash, Fenster bewegt sich nicht. Verifiziert über On-Screen-Liste (unverändert) + Screenshot.
- **Klassen-Introspektion (26.5):** `performWithWMBridgeDelegate` ist vom Parent `SLSAsynchronousBridgedWindowManagementOperation` geerbt; das Kind überschreibt `invokeFallback` (= eigentliche Move-Logik). Beide direkt getestet → beide No-op.
- **Offen:** Regression 26.4.1→26.5 ODER Kontext/Entitlement-Gap (in welchem Prozess-Kontext validierte ejbills?). Versions-Verdacht ist NICHT inkohärent — die Validierung war versionsspezifisch 26.4.1, und 26.5/25F71 hat belegte WindowServer-Änderungen (DockDoor #1344: WindowServer-Crash auf exakt Build 25F71). 26.4.1-Gegentest versperrt (schon auf 26.5, Downgrade unpraktikabel).

### Thread B — Produktions-Mechanismus (plain CGSMove + Detection)

Produktion (`Meta/blank` + iterative-dev-Plugin-Spiegel, byte-identisch) nutzt **NICHT** den bridged-Op, sondern plain `CGSMoveWindowsToManagedSpace`. Pipeline (spawn + show identisch bis aufs Öffnen):

1. **Sidecar** (menubar-gepflegt): `{"<cwd>": {"space_id": N, "desktop_no": N}}`. Helfer macht KEINE eigene Space-Erkennung, vertraut Sidecar.
2. **find-caller-desktop** (vor dem Öffnen): `$PPID` → `_find_claude_ancestor` → cwd via `lsof` (`_cwd_of_pid`) → Sidecar-Lookup → `space_id`. Log: `sidecar=hit space_id=N`.
3. **Öffnen:** spawn = `osascript tell Ghostty create window` (**synchron**, blockiert bis Fenster da); show = `open`/`open -a CotEditor` (async).
4. **wait-and-move-space** (bg): `_wids_for_owner_name` Schnappschuss (`CGWindowListCopyWindowInfo(_CGW_LIST_ALL=0, ...)` = ALLE Spaces, on+off-screen) → Poll-Diff (0.15s) bis neu/Timeout → `_move_windows_to_space` → `CGSMoveWindowsToManagedSpace(cid, [wid], space_id)`.

**Bugs:**

- **Detection-Ordering (Hauptbug, spawn systematisch kaputt):** osascript öffnet das Fenster synchron VOR dem `wait-and-move-space`-Schnappschuss → neues Fenster ist schon im "vorher"-Set → `neu = nachher − vorher = ∅` → `move=no-new-window` bei JEDER `op=spawn`-Logzeile. Der Move feuert nie. Show: `open` async → Timing-Rennen, mal `move=1_windows` (Log 17:43), meist `no-new-window`.
- **Natural-Landing-Illusion:** Fenster gebiert auf aktivem Space; wenn die Main den Spawn auslöst, ist deren Space der aktive → Fenster landet "richtig" OHNE dass der Move etwas tat. "Läuft doch" greift nur solange der Auslöser auf seinem eigenen Space sitzt; aus der Ferne fällt es zusammen.
- **plain CGSMove auf 26.5 UNBEWIESEN:** "tot/rights-gated" stammt aus F1/Sequoia 15.7 (alte Maschine), nie auf 26.5 nachgetestet. Selbst wenn Detection fixed + Move feuert → kein Beleg dass das Fenster sich tatsächlich bewegt.

## Architektur-Erkenntnisse

- Ein Fenster materialisiert IMMER auf dem aktiven Space; keine API erzeugt ein Fenster direkt auf einem fremden Space → Move-after-open ist der einzige Weg.
- "Background-Spawn damit User nichts sieht" = `open -g` (kein Fokus-Klau) + schnell wegziehen. Vorbehalt: kurze Materialisierung auf dem aktiven Space ist unvermeidlich.
- Move-Richtung Produktion: aktiver Space → Caller-Main-Space (nur nötig wenn aktiv ≠ Caller-Space).

## Identifikation des neuen Fensters — Designraum

Kernfrage, die die Detection beantworten muss: WELCHES der vielen Fenster ist das neue?

- **owner-PID disambiguiert NICHT** — CotEditor/Ghostty = 1 Prozess mit n Fenstern, alle teilen die PID.
- **(a) Snapshot-Diff** — IST-Verfahren, brüchig (Timing, Ordering-Bug).
- **(b) Titel-Match** — bekannter eindeutiger Titel (Dateiname / tmux-Session, von UNS vergeben) == `kCGWindowName`. Timing-robust. Vorbehalt: `kCGWindowName` ist in launchd/bundle-Kontext TCC-gestrippt (Etappe-2-Befund), aus CC-/Worker-Kontext aber verfügbar. **Favorit.**
- **(c) frontmost** — erstes Fenster der App (front-to-back-Ordnung von `CGWindowListCopyWindowInfo`) direkt nach dem Öffnen.

G3-Probe testet (b)+(c) gegen (a) als Grundwahrheit + sichere Space-Erkennung des neuen Fensters.

## Forward-Plan

1. **G3 (läuft):** Detection-Probe — 3 Fenstertypen (tmux-Ghostty, plain-Ghostty, CotEditor), Methoden (b)+(c) vs (a), + sichere Space-Erkennung des neuen Fensters (CGSGetActiveSpace + On-Screen-Membership + CGSCopySpacesForWindows, gegengecheckt). KEIN Move. Report: Fenster gespawnt/Programm × erkannt/Space.
2. **Danach:** plain `CGSMoveWindowsToManagedSpace` auf 26.5 isoliert verifizieren (echte Move-Wirkung, On-Screen-Liste + Screenshot) — die in G2 versäumte richtige Primitive.
3. Wenn (2) wirkt + (1) zuverlässig → Detection-Fix (**Schnappschuss VOR dem Öffnen**, Auftrennung von wait-and-move-space; in blank + Plugin-Spiegel) ist der vollständige Produktions-Fix.
4. Wenn (2) nicht wirkt → andere Move-Technik nötig, Thread A (Regression vs Kontext) weiterverfolgen.

## Orchestrierungs-Lehre

G2-Mission war relativ zum G1-Plan KORREKT (bridged-Op war DIE auf 26.4.1 verifizierte Technik, korrekt getestet). Opus-Fehler: G2-Ergebnis + User-Spawn-Beobachtung vermengt → vorschnell "falsche Primitive / Versions-Blame inkohärent". Korrektur: zwei getrennte Threads. Detection-first (User-Direktive) ist der richtige Einstieg, weil Thread B unabhängig von Thread A reparierbar UND verifizierbar ist.

## Abschluss (2026-05-31)

### Detection (Thread B) — GELÖST, dann zurückgebaut
G3 (`G3_window_detection_probe.md`): Schnappschuss-VOR-Öffnen erkennt das neue Fenster zuverlässig (9/9), Space-Bestimmung für Ghostty 6/6 (alle 3 Signale einig). CotEditor-Fix quellbelegt (DockDoor `AppDelegate.performOnLaunchAction` feuert nur bei Kaltstart → `open -n` vermeiden, plain `open` + Dateiname-Match): danach 3/3 erkannt. Robuster Identifikations-Anker = **Dateiname-Match** (z-Order-unabhängig). Detection war also voll machbar — aber sie diente nur dem Move, der unmöglich ist → mit zurückgebaut.

### Move (Thread A + B) — BEWIESEN UNMÖGLICH SIP-frei auf 26.5
G4 (`G4_move_sweep_probe.md`): Permission-Selbsttest zur Laufzeit `AXIsProcessTrusted()=True` UND `CGPreflightScreenCaptureAccess()=True` (echtes Homebrew python3.14, keine TCC-Identitäts-Verwechslung). Trotzdem **alle 5 Move-Primitiven no-op**: bridged-op (G2), `CGSMoveWindowsToManagedSpace`, `SLSMoveWindowsToManagedSpace`, `CGSAddWindowsToSpaces`+`Remove`, `SLSSpaceSetCompatID`+`SLSSetWindowListWorkspace`. → Berechtigung ist NICHT der Gate (Accessibility-Hypothese widerlegt).

DockDoor-Entitlements-Beleg: keine privaten `com.apple.private.skylight.*` Entitlements — nur AppleEvents + Sparkle + Kalender. DockDoor verlangt `AXIsProcessTrusted()` (Accessibility) + `CGPreflightScreenCaptureAccess()` (Screen Recording) — beide hatten wir. Also kein Apple-Signing-Geheimnis.

Ökosystem-Verdikt (finale gh-Recherche): yabai #2789 — User auf 26.5 findet via LLDB, dass `SLSPerformAsynchronousBridgedWindowManagementOperation` "just doesn't work sometimes", muss ihn auf NULL setzen für Fallback auf Dock-Injektion. yabai #2634 — `move_space` in der 26er-Dock-Binary nicht mehr auffindbar. Hammerspoon #3636 — `moveWindowToSpace` hacky, "unzuverlässig bis Apple eine API liefert". **AeroSpace** (populärer moderner SIP-freier WM) benutzt native Spaces bewusst NICHT ("considerable limitations") und emuliert eigene Workspaces per Off-Screen-Positionierung (Accessibility-Position, SIP-frei) — das ernsthafteste Projekt hat native-Space-Move aufgegeben. Jeder funktionierende Tahoe-Move = SIP-off + Dock-Scripting-Addition (User abgelehnt: kein Sicherheits-Trade-off).

**Fazit:** kein SIP-freier, unprivilegierter Weg, ein Fenster zwischen nativen macOS-Spaces auf 26.5 zu verschieben. Bewiesenes Negativ, kein offener Zweifel.

### Rollback ausgeführt
- **Monitor_CC menubar** (commit `466f327`+`f81b283`, gemergt `747e47f`): `desktop_detection.py` gelöscht; `discover.py` Sidecar-Writer + `desktop_no`-Feld raus; `paths.py` `CWD_DESKTOP_FILE` raus; `panel.py`/`panel_manager.py` zurück auf sequenzielle Slot-Nummern `[N]`; `setup_py2app.py` `NSScreenCaptureUsageDescription` raus (Detection-only); DOCS aktualisiert. Import-Smoke grün, −450 Zeilen.
- **Meta/blank = iterative-dev-Plugin-Source** (commit `1926c50`+`89f1797`, gemergt `3441aaa`, published): `src/desktop/desktop_targeting.py` + Verzeichnis gelöscht; `tmux_spawn.sh` `open_tmux_viewer` Placement raus (Signatur `SESSION`, beide Caller); `bin/show` Placement + totes `app_name` raus. `bash -n` grün, Cache verifiziert placement-frei. Spawn öffnet jetzt das Fenster nur noch (natürliche Aktiv-Space-Platzierung).
- **Bleibt als Beweis:** `dev/desktop_detection/` Probes 01–06, `decisions/OldThemes/desktop_allocation/` G1–G4 + H1.
