# Dolt Server Lifecycle — bd↔dolt Restart-War (2026-05-29)

## ✅ RESOLVED 2026-05-30 — bd v0.60.0 → v1.0.4 Upgrade, Loop tot, null Datenverlust

**Fix:** bd upgegradet (Option A) — Restart-Loop behoben. v1.0.4 hält den auto-gestarteten dolt-Server am Leben (PR #2655-Klasse) statt ihn pro Command zu churnen. Damit war es der #2655/#2675-Mechanismus, nicht eine v0.60-Sondervariante — das offene Gate aus dem KORREKTUR-Block ist geklärt.

### Install — kontrollierte Single-Version (kein Auto-Update)
- Binary `beads_1.0.4_darwin_arm64.tar.gz` (checksum-verifiziert gegen `checksums.txt`, `0c53479…`) nach `~/.local/bin/bd` (PATH-Position 1, vor `/opt/homebrew/bin`). `bd version` → 1.0.4 (ce242a879).
- `brew uninstall bd` (alte Tap-Formula `steveyegge/beads`, v0.60.0 entfernt, Symlink weg). **`brew pin dolt`** (dolt 1.83.5 eingefroren — bd braucht es als Subprozess).
- Kein Paketmanager mehr, kein Self-Update: `bd upgrade` ist nur ein lokaler Versions-Change-DETEKTOR (`cmd/bd/upgrade.go`, kein Netzwerk/Download — schreibt nur `metadata.json` + vergleicht). npm-Paket `@beads/bd` bewusst NICHT genutzt (publiziert die gesperrte 1.0.5 + Node-Shim-Schicht). Homebrew: kein `autoupdate`-Tap, keine launchd-Jobs → upgradet Binaries nie von selbst.
- **Gesperrt:** v1.0.5 (Prerelease) enthält Migration `0043`, die Multi-Machine-`bd dolt`-Sync "silently and unrecoverably" zerstört (#4259) — Homebrew auf v1.0.4 zurückgerollt. Uns irrelevant: keine dolt-Remotes (`bd dolt remote list` = none) + v1.0.4 ≠ v1.0.5.

### Migration — in-place auf Server-Store, kein Datenverlust
- v1.0.4 RESPEKTIERT `metadata.json: dolt_mode=server` → migriert in-place auf `.beads/dolt/` (Server-Modus bleibt, KEIN Wechsel zu `.beads/embeddeddolt/`). Schema-Stempel 0.60.0 → 1.0.4 via `bd migrate --yes`.
- **Datenverlust-Risiko per Wegwerf-Sandbox ausgeschlossen:** Kopie von Monitor_CCs `.beads` migriert → der jüngste Issue (29.05., noch nicht in die wochenalte `issues.jsonl` geflusht) überlebt, Issue Count 248 erhalten. Beweis, dass auf den echten DB-Daten migriert wird, nicht auf der stale JSONL. Die `auto_import_upgrade`-JSONL-Recovery ist emptiness-guarded + insert-if-new (`importFromLocalJSONLConflictSkip`, GH#3955) → auf nicht-leerer DB harmloser No-op, kann Live-Daten nicht überschreiben.
- **7 Projekt-DBs migriert** (alle 1.0.4, Counts erhalten): Monitor_CC 248, Trading 15, blank 38, searxng 83, RAG 88, github 32, Reddit 35. `bd migrate` flusht die JSONL nebenbei wieder aktuell.
- **arxiv + linkedin** bewusst ausgeklammert, Migration fehlgeschlagen (kein Datenverlust): arxiv `.beads/dolt/` enthält nur `config.yaml` (keine echte DB); linkedin auf fixem Port 3307 / Shared-Server (offline). Menubar loggt dafür harmlose Open-Errors. Nicht weiterverfolgt.

### Verifikation — Loop tot
- 3× `bd list` in Folge (= das Menubar-Polling-Kommando) → identischer Port 61785, identische Server-PID 72690, 1 Server, 20s stabil, **0 Circuit-Breaker**. Im alten v0.60 hätte dasselbe Polling den Server alle ~8s neugestartet.
- Menubar via `launchctl bootout` fürs Migrationsfenster sauber raus, danach `launchctl bootstrap` zurück — 1 gesunde Instanz (`state = running`).

### Backup (Rückversicherung, kann nach Stabilitäts-Bestätigung weg)
`~/beads-upgrade-backup-20260530-213148/` (86 MB): rohe `.beads/dolt`-Dirs aller 9 Projekte + altes v0.60.0-Binary + JSONL.

---

## ⚠️ KORREKTUR 2026-05-30 — Homebrew war ein Red Herring, Wurzel NICHT behoben

Die unten dokumentierte Schlussfolgerung (Homebrew-dolt-Dienst = Ursache, `brew services stop dolt` = Fix) ist **falsch**. Beleg: der 53351-Loop kam zurück (20.715 Neustarts, +744 nach dem „Fix", 8s-Takt) — **ohne** dass der Homebrew-Dienst zurück war (`launchctl` bestätigt nicht geladen). Die Schleife pausierte 2026-05-29 ~22:55 nur durch die launchd-Respawn-Drossel (zeitlicher Zufall, 5 min vor `brew services stop`); die Lockstep-Zeitstempel waren KEIN Kopplungsbeweis. `brew services stop dolt` bleibt sinnvoll (redundanter Dienst weg), ist aber NICHT der Fix.

### Echte Wurzel (Befund 2026-05-30)
bd-interne Server-Lifecycle-Instabilität, **projektübergreifend** (Monitor_CC, searxng, … je eigener ephemerer Port — Proxy-Log `src/logs/tool_errors.jsonl` zeigt Circuit-Breaker auf 56857/59469/53351):
- **Per-Command auto-start/auto-stop** (refcounted): bd-Kommandos öffnen/schließen einen DoltStore und fahren den Server hoch/runter. Treiber: die **Menubar pollt bd kontinuierlich pro Projekt** (`bd list -l tracked --json --db <proj>`) — jeder Poll ein Start/Stop-Zyklus.
- **Circuit-Breaker** (`internal/storage/dolt/circuit.go`): 5 Fehler/60s → OPEN; Zustand in `/tmp/beads-dolt-circuit-<port>.json`, **überlebt bd-Aufrufe + Reboots**.
- **`IsRunning` prüft PID-File, nicht TCP** (beads-Issue #2341): meldet „not running" obwohl ein Prozess läuft (stale PID/Port-File durch die ständigen Restarts) → triggert KillStaleServers + Restart → Loop. Live reproduziert: `bd dolt status` = „not running" bei lebendem Prozess auf 53351.
- bd-Version lokal: **0.60.0** (91df6ef6).

### Fix-Optionen
- **A (gewählt, aufgeschoben auf nächste Session): bd upgraden.** Upstream gefixt: #2636 (v0.61.0-Regress, infinite restart loop) via PR #2675 (doctor teilt EINEN Store statt per-Check) + #2655 („keep repo-local auto-started servers alive"). **Unsicher:** #2636 ist ein v0.61.0-Regress, wir sind v0.60.0 (davor) — ungeklärt, ob unser Loop exakt der #2636-Mechanismus ist oder eine v0.60.0-Variante. **VOR dem Upgrade:** bd-CHANGELOG/Releases v0.60.0 → aktuell prüfen, was das Upgrade sonst mitzieht (Historie ruppig: v0.49→v0.58 entfernte SQLite).
- **B: Auto-Start aus + persistenter Server pro Projekt** (`dolt.auto-start: false` / `BEADS_DOLT_AUTO_START=0`). Kein per-Command-Churn; bd verbindet zum stehenden Server. Kein bd-Upgrade nötig; Server muss zuverlässig oben gehalten werden.
- **C: Menubar-Polling entschärfen** (unser Code, der Trigger). Mildert die Frequenz, behebt die Wurzel nicht.

### Nächste Session — vor dem Upgrade KLÄREN (sonst upgraden wir blind)
Zwei Verifikationsschritte, bevor Option A (Upgrade) ausgeführt wird:
1. **Tatsächlichen 8s-Trigger festnageln.** Läuft der Restart-Loop weiter, wenn KEINE bd-Calls kommen? Test: Menubar-bd-Polling kurz aussetzen (oder `dolt-server.log`-Restart-Timing bei null bd-Aufrufen beobachten). Loop hört auf → per-Command-Lifecycle (= #2636-Mechanismus, Upgrade trifft die Ursache). Loop läuft weiter → anderer Treiber (bd-Daemon / Health-Checker / Menubar-Seite), Upgrade trifft evtl. NICHT. **Offener Widerspruch:** 5 schnelle `bd list` erzeugten 0 Zusatz-Restarts → deutet darauf, dass bd-Lesen den Server in v0.60.0 NICHT stoppt (also evtl. NICHT der #2636-Mechanismus).
2. **bd-Changelog/Releases v0.60.0 → aktuell lesen.** Was liegt real zwischen unserer Version und dem #2636/#2655-Fix; welche Breaking Changes (Historie ruppig: v0.49→v0.58 entfernte SQLite).

**Gate:** nur upgraden, wenn der unter (1) festgenagelte Trigger dem entspricht, was der Upgrade behebt — sonst ist es ein Blind-Upgrade.

### Recovery (temporär)
Breaker-Files `/tmp/beads-dolt-circuit-*.json` löschen + dolt-Prozesse killen + stale LOCK/pid/port-Files weg + sauberer Neustart. Hält nicht, solange Trigger (Polling) + Lifecycle-Churn bestehen.

### Quellen (Korrektur)
beads-Issues #2636 (Loop), #2341 (Circuit-Breaker-Recovery-Guide), #2598 (Breaker vor Auto-Start); PRs #2675 (merged), #2655. Proxy-Log `src/logs/tool_errors.jsonl` (cross-project Breaker-Errors). `IsRunning`/`Start` in `internal/doltserver/doltserver.go`.

---

*Alles unterhalb ist HISTORISCH / SUPERSEDED — als Iterationsverlauf behalten (die Zwei-Server-Beobachtung war real, aber NICHT die Wurzel).*

## IST (Stand 2026-05-29) — ⚠️ SUPERSEDED (siehe Korrektur oben)
- Pro Projekt EIN dolt sql-server, lazy von bd gestartet, eigener ephemerer Port (gemerkt in `.beads/dolt-server.port`). Live: Monitor_CC 53351, Meta/blank 63303, Trading 65511 — distinkt, keine Kollision.
- Ports sind dynamisch/ephemer: KEINE Port-Config in `.beads/config.yaml` oder `metadata.json`. bd allokiert via OS-Ephemeral-Port, merkt ihn im Port-File; Clients (Menubar/Opus/Worker) finden den Port übers Port-File.
- Homebrew-launchd-dolt-Dienst `homebrew.mxcl.dolt` via `brew services stop dolt` permanent entfernt (war `RunAtLoad`+`KeepAlive`, `dolt sql-server` auf `localhost:3306` + `/tmp/mysql.sock`).
- bd-Server stabil: Neustart-Zähler eingefroren bei 19.971, >16 min ohne Neustart nach Entfernen des Homebrew-Konkurrenten (vorher 1 Neustart / ~8 s).

## Symptom (Ausgangslage)
bd-Operationen brachen periodisch mit „circuit breaker open" ab. Arbeitsannahme: „dolt sql-server stirbt nach ~2 min Uptime + hinterlässt Orphans".

## Falsche erste Wurzel (verworfen)
Theorie 2026-05-28: TIME_WAIT-Stau auf fixem Port 53351 (Connection-Churn durch Menubar-7s-Polling + Worker + Opus) + Orphan-Dolt-Prozesse + 10s-Bind-Timeout → Bind-Fail → Client-Circuit-Breaker. Lösungsidee damals: `.port`-Datei löschen, damit bd frischen Port statt TIME_WAIT-Port nimmt.
→ **Verworfen.** Server stürzt nie ab (Log sauber), und der Port ist gar nicht fix konfiguriert (ephemer, nur im Port-File gemerkt). Idle-Shutdown ebenfalls aus (`idle-timeout: "0"` in `config.yaml`). Damit ist auch die „frischer-Port"-Idee gegenstandslos.

## Echte Wurzel (Befund 2026-05-29): Zwei-Server-Kill-Krieg
- **Log-Befund:** bd-Server (53351) crasht NIE — 0 Treffer für panic/signal/oom/killed in 34 MB Log über 2,5 Monate — wird aber alle ~8 s frisch neugestartet (19.857 „Server ready" seit März).
- **bd-Mechanik** (`gastownhall/beads`, vormals `steveyegge/beads`, `internal/doltserver/doltserver.go`):
  - `EnsureRunningDetailed` adoptiert den laufenden Server NUR wenn `IsRunning()==true`; sonst → `Start()`.
  - `Start()` ruft `KillStaleServers()` (Stderr-Msg „Info: cleaned up N orphaned dolt sql-server process(es)") und killt per `proc.Kill()` (SIGKILL) `dolt sql-server`-Prozesse, die nicht der kanonische PID sind. Cleanup läuft im Lock (GH#2430: sonst Journal-Korruption bei konkurrierenden bd-Prozessen).
  - **Routine-Reads lösen den Restart NICHT aus:** 5 schnelle `bd list --db .../.beads/dolt` (exakt das Menubar-Kommando) → 0 Neustarts, alle adoptieren sauber. Damit ist Menubar-Polling als Treiber widerlegt (war erste Sub-These, ebenfalls falsch).
- **Zweiter Akteur:** Homebrew-launchd-Dienst `homebrew.mxcl.dolt` (`~/Library/LaunchAgents/homebrew.mxcl.dolt.plist`): `KeepAlive=true`, `RunAtLoad=true`, `dolt sql-server --config /opt/homebrew/etc/dolt/config.yaml` auf `localhost:3306` + `/tmp/mysql.sock`. `launchctl list` zeigte Exit-Status `-9` (SIGKILL).
- **Kopplung bewiesen (Lockstep-Zeitstempel):** bd-Server letzte Neustarts …22:55:30 / :37 / :45; Homebrew …22:55:30 / :41 / :52 — beide im Gleichschritt, beide gleichzeitig gestoppt (7 s auseinander).
- **Krieg-Mechanik:** bd's `KillStaleServers` erschießt den Homebrew-dolt (SIGKILL = das `-9`) → launchd respawnt ihn (KeepAlive) → die laufende Population von `dolt sql-server`-Prozessen lässt bd's Adoption fehlschlagen → bd rebootet seinen eigenen Server → Schleife ~8 s, auf beiden Seiten.
- **Warum es um 22:55 von selbst aufhörte** (vor dem manuellen Eingriff um 23:00:43): launchd-Respawn-Drossel — der Homebrew-Dienst starb zu schnell zu oft, launchd gab das Respawnen auf → Homebrew-dolt weg → bd-Gegner weg → bd-Schleife endet. **Temporär:** `RunAtLoad` hätte ihn beim nächsten Login wiederbelebt und den Krieg neu gestartet.

## Fix
`brew services stop dolt` — entfernt den Dienst aus dem Boot-Set (kein `RunAtLoad`-Respawn mehr). Dolt-**Binary** bleibt installiert (bd braucht es). Permanent + reboot-sicher.
- **Verifikation:** `launchctl list` listet `homebrew.mxcl.dolt` nicht mehr; einziger lebender `dolt sql-server` = bd's Projekt-Server (53351); bd-Neustart-Zähler eingefroren.
- **Reststaub:** verwaister `/tmp/mysql.sock` (harmlos).

## Dynamische Ports — Bewertung
Bereits dynamisch/ephemer (3 distinkte Ports, keine Config). „Komplett auf dynamische Ports / frischen Port pro Neustart erzwingen (Port-File löschen)" → **nicht empfohlen**: adressiert die echte Ursache (Zwei-Server-Krieg, behoben) nicht und bringt Client-Race-Risiko im Port-Wechsel-Fenster. Port-Kollision zwischen Projekten aktuell nicht vorhanden; `.beads/` ist gitignored → kein versehentliches Port-File-Kopieren. Ist-Design (ephemer + Port-File-Rendezvous) ist korrekt.

## Verbleibende Folge-Themen
- **Worker-Spawn-Härtung:** Spawn übergibt den Prompt als Kommandozeilen-Argument (`claude "$(cat prompt)"`) → Worker-cmdline trägt beliebigen Prompt-Text → angreifbar für JEDEN Cmdline-Match-Kill. Konkret: bd's dolt-Cleanup killte 2× einen Worker beim Start, dessen Prompt den String „dolt sql-server" enthielt. Echter Fix: Prompt via stdin/Datei statt Argument (Spawn-Infra `tmux_spawn.sh` im iterative-dev-Plugin, cross-project). Dringlichkeit nach Homebrew-Fix gering (Cleanup feuert kaum noch). **KEIN Hook-Fix möglich:** bd's Kill ist internes Go (`proc.Kill()`), für PreToolUse-Bash-Hooks unsichtbar.
- **Orphan-Cleanup-Meldung:** nach Homebrew-Fix nur noch one-liner beim echten Initial-Start, kein Dauerrauschen. (Allgemeines Tool-Error-Noise-Stripping bleibt separates, datenabhängiges Thema.)
- **Verwandt (Projekt blank):** bd/Dolt auto-start fragility (port collisions + 10s timeout + kein Fallback) — eigenes Thema dort.

## Quellen
- `gastownhall/beads` (vormals `steveyegge/beads`) `internal/doltserver/doltserver.go`: `EnsureRunningDetailed`, `Start`, `KillStaleServers` / `killStaleServersForDir`, `IsAutoStartDisabled`, `IsRunning`, `allocateEphemeralPort`. GH#2430 (Journal-Korruption → Cleanup-im-Lock), GH#2554 (shared server), GH#2641 (auto-start disable), GH#3142 (10s `readyTimeout`).
- Live: `.beads/dolt-server.log`, `/opt/homebrew/var/log/dolt.error.log`, `~/Library/LaunchAgents/homebrew.mxcl.dolt.plist`, `launchctl list`.
