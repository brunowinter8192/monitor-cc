# D1 — blank Desktop-Targeting Robustheit via Menubar-Sidecar (2026-05-28)

**Status:** Entscheidung getroffen, NICHT implementiert. Sequenziert NACH dem Menubar-Refactor (Bead g15z). Cross-repo: Monitor_CC (Menubar publiziert) + Meta/blank (Helper konsumiert).

## Kontext

Etappe 3 (Worker-Spawn auf Caller-Desktop) + Etappe 4 (File-Open via `show`) sind in `Meta/blank` commit `cfd0d14` implementiert, aber best-effort. User-Ziel: beide Platzierungen sollen **immer** sitzen, nicht nur best-effort.

`Meta/blank/src/desktop/desktop_targeting.py` ist die naive Vorgängerversion der Menubar-Detection. Es bricht reproduzierbar — User verwies auf den `n_cand=0`-Effekt (dokumentiert in `C3_detection_logging.md`).

## Root-Cause (verifiziert durch Vollständig-Read beider Files, 2026-05-28)

`desktop_targeting.py` fehlen drei Robustheits-Mechanismen, die `src/menubar/desktop_detection.py` (verifiziert, 100% Detection-Rate) hat:

| Mechanismus | Menubar `desktop_detection.py` | blank `desktop_targeting.py` |
|---|---|---|
| Titel-Quelle | `CGSCopyWindowProperty` Key `kCGSWindowTitle` (SkyLight, TCC-bypass) | `kCGWindowName` roh (leer in TCC-Restriction) |
| Spinner-Normalize | `_normalize_window_title` strippt CC-Spinner-Glyph von beiden Seiten vor Match | keiner → Mismatch sobald Spinner asymmetrisch |
| Resolver | 3-Stufen: name-unique → space-elimination → OSC-2-Injection (`_resolve_cgwindow_id`) | nur Stufe 1; `len(wids) != 1 → None` |

Der Spinner-Mismatch allein erzeugt `n_cand=0` unabhängig vom Spawn. Der fehlende Fallback macht jeden Mehrdeutigkeits- oder Cache-Churn-Fall zum Totalausfall.

## Wege erwogen

**Weg 1 — Port der 3 Mechanismen nach blank.** Rein blank-seitig, sofort machbar, kollidiert nicht mit Refactor. Für Single-Caller ist OSC-2-Injection auf die tty des Aufrufers besonders stark (markiert Fenster direkt statt Namens-Raten). Nachteil: dritte Kopie derselben CGS-Logik (Probe / Menubar / blank) → Drift-Hazard.

**Weg 2 — Menubar publiziert verifiziertes Ergebnis als Sidecar ← GEWÄHLT.** Menubar detektiert ohnehin alle 10s robust und kennt pro Main die Space-ID. Sie schreibt `cwd → space_id` (last-known-good) in eine JSON; blank-Helper liest nur noch aus, macht selbst keine fragile Detection mehr.

## Gewählt: Weg 2

**Reasoning:**
1. Keine dritte Kopie der CGS-Detection — blank konsumiert direkt die geprüfte Pipeline.
2. Robuster gegen den Spawn-Moment: last-known-good überbrückt den transienten `n_cand=0`-Einbruch (Main-Space-ID ist stabil, Menubar kannte sie aus früheren Cycles).
3. blank hängt ohnehin schon an der Menubar (liest `ghostty_cwd_uuid.json`) — Weg 2 vertieft die bestehende Kopplung, fügt keine neue hinzu.

Trade-off akzeptiert: braucht Menubar-Source-Änderung → deshalb sequenziert nach dem Refactor (Menubar gerade im Umbau, Kollision vermeiden).

## Implementierungs-Skizze (für Pickup nach Refactor)

**Menubar-Seite (Monitor_CC, Worker-Task — current project):**
- `desktop_detection.py` / `discover.py`: verifiziertes Result als `cwd → {space_id, desktop_no}` in APP_SUPPORT-Sidecar persistieren (z.B. `cwd_desktop.json` neben `ghostty_cwd_uuid.json`).
- **Last-known-good:** transientes None NICHT über einen guten space_id schreiben — alten Wert behalten bis neuer gültiger kommt.
- space_id ist der stabile Identifier für den Move (`CGSMoveWindowsToManagedSpace` nimmt space_id, nicht desktop_no) — muss mit raus, Menubar exponiert ihn bisher nur in-memory.

**blank-Seite (Meta/blank, Opus direct — cross-repo):**
- `desktop_targeting.py`: Caller-Identification behalten (parent-walk → claude → lsof → cwd), dann cwd im Menubar-Sidecar nachschlagen → space_id. Fragile Namens-Match-Kette (`_ghostty_uuid_to_window_name` → `_windows_by_name_for_pid` → `len(wids)!=1`) entfällt.
- Window-Move + New-Window-Polling-Primitiven bleiben (nicht der fragile Teil).
- **Detect-before-disturb:** Caller-space_id VOR dem auslösenden Open/Spawn ermitteln (Landschaft stabil), danach nur noch neues Fenster pollen + verschieben. Greift bei beiden Wegen; aktuell läuft Detection nach dem Open.

**Logging (blank-seitig, eigener Sink — NICHT Monitor-Logging):**
- Separater blank-Log (eigene Datei, nicht `menubar.log`).
- Für Worker-Spawn (`tmux_spawn.sh:open_tmux_viewer`) UND File-Open (`bin/show`): caller_pid, aufgelöste claude-cwd, space_id aus Sidecar (oder Miss-Grund), Window-Poll-Resultat, Move-Resultat.
- Ersetzt die aktuelle `>/dev/null 2>&1`-Stille — alle 6 Stufen müssen diagnostizierbar werden.

## Offene Fragen

- Worker-`show`: ruft ein Worker (kein Main) `show` auf, findet die Caller-Identification den Worker-Claude (cwd=Worktree, nicht im Sidecar). Soll Worker-`show` auf den Worker-Desktop oder den des Eltern-Mains? — noch nicht entschieden.
- Multi-New-Window: `wait_for_new_windows_and_move` verschiebt ALLE neuen Fenster im Poll-Fenster; bei `app_name=""` (cross-app Poll) Risiko dass unrelated Fenster mitgezogen wird. Disambiguierung offen.
- Sidecar-Schreibfrequenz vs. Staleness: 10s Detection-Cache der Menubar vs. Spawn-Timing.

## Quellen

- `src/menubar/desktop_detection.py` (verifizierte 3-Stufen-Detection — Vorlage)
- `Meta/blank/src/desktop/desktop_targeting.py` (naive Vorgängerversion — Ziel)
- `Meta/blank/bin/show`, `Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer` (Aufruf-Pfade)
- `C3_detection_logging.md` (n_cand=0 Trigger-Doku)
- `00_design_overview.md` (Etappe 3+4 Kontext)
- `decisions/OldThemes/file_open_routing.md` (CotEditor + Desktop-Awareness IST)
