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
   - Ruft danach `_normalize_user_content_shape()` auf: User-Messages deren Content nach dem Strip `[{"type":"text","text":"X"}]` ist (single text block, exakt `{type,text}` Keys) werden auf plain string `"X"` kollabiert. Hintergrund: CC sendet User-Msgs nativ als String wenn keine BP drauf liegt, als list-with-block wenn BP drauf ist. Ohne Normalisierung gibt das Byte-Diff zwischen Requests wenn BP4 von einer Msg wegzieht. Siehe `cache_rebuild_cases.md` Case 1 (2026-04-12, commit 0f847b0).

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

### Tool-Stripping

`TOOL_BLOCKLIST` (frozenset) in `proxy_addon.py` entfernt 21 ungenutzte Tools aus dem `tools`-Array vor dem API-Send. ~25k chars weniger pro Request. Agent-Tool bleibt, aber Description getrimmt auf git-committer-only (~300 chars statt 10k).

### Live-Copy Isolation

`claude_proxy_start.sh` kopiert `proxy_addon.py` nach `$LOG_DIR/.proxy_addon_live.py` beim Start. mitmproxy lädt die Kopie. Git-Merges auf das Original triggern keinen Hot-Reload. Cleanup bei Proxy-Stop.

### Log-Naming & Rotation

Log-Dateien: `api_requests_{projektname}_{timestamp}.jsonl` statt kryptischer MD5-Hashes. Max 30 Dateien, älteste werden bei Proxy-Start gelöscht.

### Diagnostics: Prefix-Hash Instrumentation

Seit Commit `f9e4b09` (2026-04-12) schreibt `_build_sent_meta` in addon.py vier zusätzliche Felder pro `sent_meta`-Entry:

- `prefix_hash_bp1_sys` — MD5[:10] von `json.dumps(system[0:bp1_idx+1])`
- `prefix_hash_bp2_tools` — MD5[:10] von `json.dumps({"system":..., "tools": tools[0:bp2_idx+1]})`
- `prefix_hash_bp3_msg` — MD5[:10] inkl. `messages[0:bp3_idx+1]`
- `prefix_hash_bp4_msg` — MD5[:10] inkl. `messages[0:bp4_idx+1]`

Serialisierung via `json.dumps(...).encode("utf-8")` — matcht byte-genau was mitmproxy in Zeile 80 von `request()` ans API-Wire schickt.

Zweck: Byte-genauer Vergleich von BP-Prefix-Bytes zwischen aufeinanderfolgenden Requests, um zu unterscheiden ob Cache-Misses durch Byte-Drift im Prefix (dann sichtbar als Hash-Änderung) oder durch etwas außerhalb des Payloads (Header, Account-State, Fingerprint — dann alle Hashes gleich trotz Cache-Miss) verursacht werden.

Nutzung: Dev-Script liest `sent_meta`-Einträge aus `api_requests_*.jsonl`, vergleicht paarweise `prefix_hash_bp*` pro Request-Boundary.

### Granular Hash Fields + Drift Report (ab Commit feat/prefix-hash-instrumentation)

`_build_sent_meta` schreibt zusätzlich pro-Element-Hashes und einen automatischen Drift-Report:

**Hash-Felder:**
- `sys_block_hashes: list[str]` — MD5[:10] pro System-Block (Index 0..N-1). Erkennt wenn ein einzelner Block sich ändert.
- `tool_hashes: list[str]` — MD5[:10] pro Tool. Erkennt Tool-Änderungen (nicht nur Append am Ende).
- `msg_hashes: list[dict]` — Kompaktes Message-Hash-Array:
  - First 10 Messages: `{"idx": i, "role": "user|assistant", "hash": "xxxxxxxxxx"}`
  - Middle (idx 10 bis N-6): `{"idx": "10-N-6", "role": "middle", "hash": "count=K,rolling=xxxxxxxxxx"}` — rolling = MD5[:10] der verketteten middle-Hashes
  - Last 5 Messages: einzeln wie first 10
  - Bei N≤15: kein middle-Eintrag, alles einzeln
- `msg0_block_hashes: list[str]` — MD5[:10] pro Content-Block in messages[0]. Block 0 = injizierter project-rules Block (sollte nach Fixation session-stabil sein).

**Drift-Report:**
- `drift_report: dict` — Automatischer Vergleich gegen vorherigen Request (aus `self.prev_sent_hashes_by_model`):
  - Erster Request der Session: `{"initial": True}`
  - Folge-Requests: `{"sys": [geänderte_indices], "tools": [geänderte_indices], "msgs": [geänderte_indices], "msg0_blocks": [geänderte_indices]}`
  - `sys`: alle Indices mit Byte-Änderung
  - `tools`: nur Indices < min(len(prev), len(curr)) — neue Tools am Ende sind expected, werden nicht gemeldet
  - `msgs`: nur Indices < N-2 (letzte 2 Messages = neuer Turn, expected)
  - `msg0_blocks`: alle Indices — Block 0 sollte nach Fixation immer leer sein

Zweck: Drift in should-be-stable Prefix-Feldern wird automatisch pro Request sichtbar. Kein manuelles Pairwise-Vergleichen im Dev-Script nötig. Ein `drift_report.sys != []` oder `drift_report.msg0_blocks != [0]` nach dem ersten Request ist ein direktes Signal für ein Fixation-Problem.

### Session-State Fixation (ab Commit feat/prefix-hash-instrumentation)

`ProxyAddon` hält einen `self.fixated: dict` (keyed by model_family). Zweck: sys[2] und msg[0]-Projektregeln-Block werden nach dem **ersten Request** einer Proxy-Session eingefroren. Alle Folge-Requests bekommen byte-identische Bytes für diese Felder — unabhängig davon ob die zugrundeliegenden Rule-Files auf Disk geändert werden.

**Warum nur model_family als Key:** Der Proxy-Prozess lebt für eine Session. Model-family ist der einzige Splitfaktor (opus vs. sonnet vs. haiku lädt unterschiedliche Rules). Bei Proxy-Restart wird `self.fixated` resettet — der erste Request lädt neu.

**Was fixiert wird:**
- `sys2_text` — Der Text-Content von `system[2]` nach `apply_modification_rules()`. Das ist der Inhalt den `_load_system2_rules()` produziert (global + model-spezifische Rule-Files).
- `msg0_pr_block` / `msg0_pr_block_str` — Der injizierte `<system-reminder>…</system-reminder>` Block aus `_load_project_rules()`, der als erstes Content-Element in messages[0] eingefügt wird. List-content speichert `msg0_pr_block` (der Block-Text), String-content speichert `msg0_pr_block_str` (Prefix bis `</system-reminder>` inkl.).

**Was NICHT fixiert wird:**
- sys[0], sys[1], sys[3] — Claude Code kontrolliert, unberührt
- messages[1..N-1] — session-volatil per Design
- tools[] — append-only, unberührt

**Implementierung:** Rein in `addon.py`, keine Änderung an `rules.py`. Nach `apply_modification_rules()` wird entweder gecaptured (erster Request) oder via `_apply_fixation()` überschrieben (Folge-Requests). `apply_modification_rules()` läuft immer vollständig durch (kein Short-Circuit) — der Overhead ist minimal (mtime-basiertes File-Caching in `_read_rule_file()`), die Bytes werden danach überschrieben.

**Edge Cases:**
- Content `"."` (nach stripping geleerte Messages) — kein `</system-reminder>` Marker, `_capture_fixation` speichert nichts, `_apply_fixation` ändert nichts, kein Crash.
- Haiku (model_family="haiku") — `_load_system2_rules` gibt `""` zurück → sys[2] wird `"."`. Auch für Haiku wird fixated gespeichert (mit `"."`) damit der zweite Request nicht durch Datei-mtime-Änderungen abweicht.

## Recommendation (SOLL)

Keep (no change needed) — eigene Breakpoints sind implementiert und verifiziert. TTL `1h` und `scope: "global"` korrekt auf Markern gesetzt.

### Global Rules Caching

Change: Hook-injizierte Rules (78k chars, `SessionStart hook additional context:`) werden aus MSG[0] extrahiert und als eigener System-Block mit `scope: "global"` eingefügt. System-Block Position: nach system[2] (stripped), vor dynamischem Content (gitStatus). BP1 zielt auf den Rules-Block statt auf den letzten System-Block.

Erwarteter Impact: ~25-30k Tokens CR statt CC ab dem 2. Request jeder Session. Cross-session Cache-Hits bei unveränderten Rules. Cross-model: Opus + Worker mit gleichen Rules → Cache-Hit.

### Rejection Message Stripping

Change: ESC-Abbruch tool_result Messages ("The user doesn't want to proceed with this tool use...") werden auf `"."` gekürzt. Marker: `_REJECTION_MARKER` Konstante.

### Agent-Tool Trimming

Change: Agent-Tool bleibt im tools-Array, aber Description von ~10k auf ~300 chars getrimmt (nur git-committer Subagent-Type). `AGENT_TRIMMED_DESCRIPTION` Konstante.

### Session-Guidance Stripping

Change: `# Session-specific guidance` Sektion aus system[3→4] entfernt. `# Environment`, `# Language`, `gitStatus` bleiben erhalten.

### Worker Proxy Live-Copy

Change: Worker-Proxies verwenden jetzt ebenfalls Live-Copy (`.proxy_addon_worker_{name}.py`). Verhindert Hot-Reload bei Git-Merges auf proxy_addon.py. Fix in iterative-dev Plugin `tmux_spawn.sh`.

### Proxy Log-Naming

Change: Main-Logs heißen `api_requests_opus_{project}_{timestamp}.jsonl`, Worker-Logs `api_requests_worker_{name}_{timestamp}.jsonl`. Klare Trennung zwischen Opus und Worker Proxy-Logs.

### API Constraints (Referenz)

- Max 4 Breakpoints pro Request
- `defer_loading=true` und `cache_control` auf dem gleichen Tool = API Error
- Min cacheable prefix: 2048 Tokens (Opus) / 1024 (Haiku)
- Cache Write kostet 125% der Token — falsches Placement kann teurer sein als kein Caching
- cache_control marker: `{"type": "ephemeral"}` (kein TTL nötig, API bestimmt)
- `scope: "global"` — Content-basierter Cache über Sessions/API-Keys hinweg. Gleicher Content = Cache-Hit, unterschiedlicher Content = separate Einträge. Kein Cross-Contamination zwischen Opus und Worker.

## Offene Fragen

- Langzeit-Stabilität: Verhalten bei Sessions >500 Requests noch nicht beobachtet
- Claude Code Updates könnten cache_control Handling ändern (z.B. mehr als 2 eigene Breakpoints) — `_strip_all_cache_control` entfernt alles, daher robust gegen Änderungen
- Global Rules Caching: `scope: "global"` auf eigenen System-Blöcken verifizieren — cross-session Cache-Hit testen (gleiche Rules, neue Session → CR statt CC?)

## Quellen

- Anthropic API Docs: Prompt Caching (cache_control Semantik, Breakpoint-Limits)
- Proxy-Log-Analyse: `src/logs/api_requests_f93afc17.jsonl` (825MB, Session vom 2026-04-08)
- Session-JSONL-Analyse: `a3b6577a-8f2c-4cef-a594-15aa18c0f520.jsonl` (CR/CC/D Werte)
- Dev-Script: `dev/session_analysis/04_cache_validation.py`
