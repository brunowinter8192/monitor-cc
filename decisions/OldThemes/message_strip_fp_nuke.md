# Message-Strip False-Positive — File-Reads auf Placeholder genukt

Session 2026-06-22/23 (Opus). **Root Cause bestätigt (Ground-Truth), Fix angewandt, Live-Verify in nächster Session offen.**

## Problem (Symptom)

Datei-Reads über das Read-Tool kamen als nuked Placeholder statt mit Inhalt zurück. Reproduzierbar an `decisions/pipe05_proxy_cache.md`: vollständiges Lesen → genukt; `pipe02`/`pipe04` lasen sich normal. Ursache-Ebene: der laufende Monitor-Proxy modifiziert ausgehende Anthropic-Requests via `apply_modification_rules()` (`rules.py`); der Read-tool_result wandert als Teil des nächsten Requests durch den Proxy und wird ersetzt → das Modell sieht nur den Placeholder.

## Root Cause — BESTÄTIGT: `_apply_first_pass` Plan-Mode-Branch

Nicht `_apply_role_system_strip` (war der Verdacht der vorherigen Session, widerlegt — siehe unten). Schuldig ist der **Plan-Mode-Branch** in `_apply_first_pass` (`message_passes.py`).

Mechanik:
1. Detection via `_content_contains(content, "Plan mode is active")` — diese Funktion **steigt in `tool_result`-Content ab** (nicht top-level-only).
2. pipe05 enthält den String `"Plan mode is active"` **genau einmal**, in **Zeile 13** (Doku der Strip-Regel `removed_plan_mode_sr`: „text-block drop bei \"Plan mode is active\""). Liegt in Z1–104.
3. Branch feuert auf dem dokumentierten String, obwohl gar kein echter `<system-reminder>`-Plan-Mode-Block da ist. `_strip_plan_mode_blocks` findet keinen echten Block → `else`-Zweig **ersetzt die ganze Message** unkonditional (`"(plan-mode reminder stripped by proxy)"`), der Read-Inhalt ist weg.

Das erklärt die content-abhängige Bisektion der Vorsession (nur Z1–104 genukt, Rest überlebt): nur Z1–104 enthält den Marker (Z13).

### Ground Truth — `_stripped.jsonl` fn_map (Session `opus_monitor_cc_1782163188`)

`fn_map` attribuiert pro Strip-Entry die verantwortliche Funktion AT WRITE TIME. Scan über alle 41 Requests:

| Request (msg idx) | Content | fn_map |
|---|---|---|
| 82a75a0b (msg 20) | pipe05 Read (numbered) | `_apply_first_pass` |
| d4022f94 (msg 22) | pipe05 head/wc | `_apply_first_pass` |
| 8dccc584 (msg 33) | pipe05 file-type/od | `_apply_first_pass` |
| bb3858c5 (msg 46) | pipe05 trigger-lines | `_apply_first_pass` |
| f996b733 (msg 64) | pipe05 Read | `_apply_first_pass` |

`_apply_role_system_strip` trifft in DEMSELBEN Log ausschließlich echte Noise: die „task tools haven't been used recently"-Nag und `<new-diagnostics>`-Blöcke (CC 2.1.176 liefert die als eigene `role=system`-Messages). Kein FP bei role_system. role=system ist konsistent Noise → der content-blinde `.`-Nuke dort ist gewollt und korrekt.

### Branch-Marker-Check pipe05

`grep -c` über pipe05 für die `_apply_first_pass`-Branch-Marker: `Plan mode is active` = **1** (Z13), `task tools haven` = 0, `deferred tools are now available via ToolSearch` = 0, `user sent a new message while you were working` = 0. Nur der Plan-Mode-Branch konnte matchen.

### Warum nur Plan-Mode FP-nukt, die anderen Branches nicht

Die übrigen `_apply_first_pass`-Branches gaten zwar auch via `_content_contains` (Substring, steigt in tool_result ab), strippen aber via `_strip_system_reminder` (template-anchored) — findet sich kein echter SR-Block, bleibt der Content unverändert (`new_msg["content"] != old_content` ist False → keine Änderung). Der Plan-Mode-Branch ist der einzige mit einem destruktiven `else`, der die ganze Message ersetzt, wenn kein echter Block gefunden wird. Das ist der Defekt.

## Fix — angewandt (diese Session, direkt, kein Worker)

- `message_passes.py`: Plan-Mode-Branch komplett aus `_apply_first_pass` entfernt (erstes `if` raus, folgendes `elif` → `if`); unbenutzten Import `_strip_plan_mode_blocks` entfernt; Funktions-Doc-Kommentar angepasst.
- `rules.py`: `_passes` = alle 10 Passes (inkl. `_apply_role_system_strip` = #1 wieder an); `_dedup_wakeup_blocks`-Aufruf wieder einkommentiert; Temp-Disable-Kommentar entfernt.
- Kein Capability-Verlust: echte Plan-Mode-SR-Blöcke (falls je) werden weiterhin von `_apply_final_sr_pass` via template-anchored Matching gestrippt, das nicht auf Doku-Strings FP-matcht. User nutzt Plan-Mode ohnehin nie.
- `py_compile` grün. Committet + gepusht auf `main`.

## Offen — Live-Verify nächste Session

Proxy lädt erst nach Restart die neue Source (frische Live-Copy). Nächste Session:
1. pipe05 voll lesen → kein Nuke mehr (Placeholder weg, echter Inhalt da).
2. role=system-Noise (task-tools-nag, new-diagnostics) wird weiterhin korrekt auf `.` gestrippt.
3. Gewollte Strips (SR-Noise, BG, etc.) funktionieren, keine doppelten Wake-Up-Blöcke (Dedup aktiv).
4. Danach: IST in `decisions/pipe05_proxy_cache.md` korrigieren (`removed_plan_mode_sr`-Abschnitt — Regel entfernt), dann den abgebrochenen Count-Audit (Issue Doku-Drift pipe02/04/05) fortsetzen.

## Relevante Symbole / Pfade

- `_apply_first_pass()` (`src/proxy/message_passes.py`) — elif-Chain, Plan-Mode-Branch entfernt
- `_content_contains()` (`src/proxy/payload_helpers.py`) — Substring-Detection, steigt in tool_result ab (Grund für FP-Gate)
- `_strip_plan_mode_blocks()` (`src/proxy/strip_sr.py`) — bleibt definiert, nicht mehr importiert/genutzt
- `_apply_role_system_strip()` (`src/proxy/message_passes.py`) — content-blinder `.`-Nuke auf role=system, korrekt, NICHT der FP
- `apply_modification_rules()` / `_passes` (`src/proxy/rules.py`) — Pass-Orchestrator, alle 10 + Dedup aktiv
- Ground-Truth-Log: `src/logs/dual_log/api_requests_opus_monitor_cc_1782163188_stripped.jsonl` (Feld `fn_map`)
- Commit-Historie: `40e071d` (role=system-Strip eingeführt — als FP-Verdacht widerlegt)
