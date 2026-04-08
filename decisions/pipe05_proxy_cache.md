# Pipe Section: Proxy Cache-Control

## Status Quo (IST)

### Proxy Modification Pipeline

`proxy_addon.py` interceptiert alle API-Requests via mitmproxy und modifiziert den Payload vor dem Senden:

1. `apply_modification_rules()` — Content-Modifications:
   - `removed_plan_mode_sr`: Entfernt "Plan mode is active" system-reminder aus User-Messages
   - `stripped_task_tools_nag`: Entfernt "task tools haven't been used" system-reminder
   - `trimmed_task_notification`: Strippt output-file/tool-use-id Tags aus task-notifications
   - `replaced_system_prompt`: Ersetzt system[2] (>5000 chars) mit "." (Logging-Reduktion)

2. `_strip_all_cache_control()` — Entfernt ALLE cache_control Marker von Claude Code:
   - system blocks, tools, messages (top-level + content blocks)

3. `_set_cache_breakpoints()` — Setzt eigene Breakpoints (max 4) auf modifiziertem Payload:
   - BP1: `system[-1]` — letzter System-Block
   - BP2: Letztes Tool OHNE `defer_loading` (defer_loading + cache_control = API Error)
   - BP3: Letzte Message die sich gegenüber dem vorigen Request NICHT geändert hat (`first_diff_index - 1` auf modifiziertem Content)
   - BP4: Letzte Message, letzter Content-Block — für nächsten Request

### State-Tracking

`self.prev_messages_by_model` speichert Message-Summaries des **modifizierten** Payloads (nicht Original). Getrennt nach model_family ("opus" / "haiku"). BP3-Berechnung vergleicht aktuelle modifizierte Messages mit vorherigen modifizierten Messages via `_compute_diff()`.

### Worker-Isolation

Jeder Worker in einem Worktree bekommt einen eigenen mitmproxy-Prozess auf eigenem Port mit eigener Log-Datei. Implementiert in `tmux_spawn.sh` (iterative-dev Plugin):
- Worker erkennt Proxy via `/tmp/.monitor_cc_proxy_<session_hash>`
- Hash basiert auf Projekt-Pfad (Worktree-Suffix wird gestrippt → gleicher Hash wie Main)
- Eigener Port (nächster freier ab Main-Port + 1)
- Eigene Log-Datei: `api_requests_<worker_session_id>.jsonl`
- Cross-Project-Worker (anderes Projekt als Main) bekommen keinen Proxy — Marker existiert nur für das Main-Projekt

### Log Pipeline

```
Main Session → mitmdump :8084 → proxy_addon.py → api_requests_<session_id>_<timestamp>.jsonl
Worker (Worktree) → mitmdump :8085 → proxy_addon.py → api_requests_<worker_hash>.jsonl
```

Beide schreiben nach `$MONITOR_CC_ROOT/src/logs/`. Monitor liest per `session_id` das richtige Log.

## Evidenz

### Problem: Claude Code's instabiles cache_control Placement

Claude Code setzt 2 Breakpoints: `system[2]` + letzte Message. Der Breakpoint auf der letzten Message wandert bei jedem Request weiter (erwartetes Verhalten). Alte Breakpoints werden entfernt.

**Kritisch:** Proxy-Modifications ändern Messages die VOR dem cache_control Breakpoint liegen. Die API sieht modifizierten Content → Prefix-Mismatch → Cache invalidiert.

Analyse der Session `a3b6577a` (148 Requests mit Modifications):
- **98%** der Requests hatten Modifications VOR dem Breakpoint
- 4 Cache-Rebuilds beobachtet:
  - REQ#0: 36k CC (erster Request, erwartbar)
  - REQ#1: 27k CC (ToolSearch-Load, erwartbar)
  - REQ#70: 93k CC, nur 9k CR (91% Rebuild)
  - REQ#133: 162k CC, nur 9k CR (95% Rebuild)
- Die 9.297 CR bei REQ#70 und #133 = exakt `system[2]` Breakpoint. Alles danach (Tools + 100+ Messages) wurde neu geschrieben.
- Gesamtkosten: 319k Tokens für Rebuilds (2% vom Total, aber 162k = ~6% Session-Limit für einen Request)

### Fix-Verifikation

Nach Implementierung der eigenen Breakpoints (Session auf test project, 14+ Requests):
- REQ#2: CR:0, CC:30.478 (erster Request, erwartbar)
- REQ#3-#14: Alle CR >30k, CC nur 150-1200 (neuer Content)
- **Kein einziger Rebuild** — auch nicht bei ToolSearch (REQ#8: CC:425)
- BP3 verhindert Cache-Invalidierung durch Modifications: modifizierter Content ist deterministisch (gleicher Input → gleicher Output), daher ist der Prefix zwischen Requests stabil

## Recommendation (SOLL)

Keep (no change needed) — eigene Breakpoints sind implementiert und verifiziert.

### API Constraints (Referenz)

- Max 4 Breakpoints pro Request
- `defer_loading=true` und `cache_control` auf dem gleichen Tool = API Error
- Min cacheable prefix: 2048 Tokens (Opus) / 1024 (Haiku)
- Cache Write kostet 125% der Token — falsches Placement kann teurer sein als kein Caching
- cache_control marker: `{"type": "ephemeral"}` (kein TTL nötig, API bestimmt)

## Offene Fragen

- Langzeit-Stabilität: Verhalten bei Sessions >500 Requests noch nicht beobachtet
- Claude Code Updates könnten cache_control Handling ändern (z.B. mehr als 2 eigene Breakpoints) — `_strip_all_cache_control` entfernt alles, daher robust gegen Änderungen

## Quellen

- Anthropic API Docs: Prompt Caching (cache_control Semantik, Breakpoint-Limits)
- Proxy-Log-Analyse: `src/logs/api_requests_f93afc17.jsonl` (825MB, Session vom 2026-04-08)
- Session-JSONL-Analyse: `a3b6577a-8f2c-4cef-a594-15aa18c0f520.jsonl` (CR/CC/D Werte)
- Dev-Script: `dev/session_analysis/04_cache_validation.py`
