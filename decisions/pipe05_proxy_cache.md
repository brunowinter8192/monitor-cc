# Pipe Section: Proxy Cache-Control

## Status Quo (IST)

### Proxy Modification Pipeline

`proxy_addon.py` interceptiert alle API-Requests via mitmproxy und modifiziert den Payload vor dem Senden:

1. `apply_modification_rules()` — Content-Modifications:
   - **SR-Strip via Template-Catalog (commit e1a3b9a, 2026-04-21):** `strip_sr.py` matcht 8 distinct SR-Templates über exakten startswith-Identifier statt greedy regex. Templates: `task-tools-nag`, `pyright-new-diagnostics`, `deferred-tools`, `user-interrupt`, `system-notification`, `file-modified`, `claudemd-contents`, `date-changed`. Operiert auf allen 4 content-shapes: top-level string, `text`-blocks in list, `tool_result.content` (string), `tool_result.content` (list of text-sub-blocks). Vorgängerversion (greedy regex `<sr>.*?</sr>`) hatte False-Positive-Bug — matchte über Code-Literale wie `if "<system-reminder>" in text:` und entfernte echten Python-Code aus Payloads. Replay über 22 historische JSONLs (~37k strips): 0 false-positives mit neuem template-based code (vorher ~970 FPs).
   - **Env-Context SR Strip (commit a26f83a, 2026-05-30):** `strip_sr.py::_apply_sr_strip._replace` prüft vor dem `_PRESERVE_PREAMBLE`-Guard via `_ENV_CONTEXT_RE.fullmatch(inner)` ob der SR-Block dem CC-injizierten userEmail/currentDate-Block entspricht. Bei Match → vollständiger Strip (`return ''`). Pre-guard-Position ist zwingend: der env-context Block hat exakt denselben Preamble wie CLAUDE.md-Kontext-Blocks (`"As you answer the user's questions, you can use the following context:"`), sodass der `_PRESERVE_PREAMBLE`-Guard zuerst feuern würde. Regex: Email literal, Datum `\d{4}-\d{2}-\d{2}`, Whitespace vor IMPORTANT via `\s+` (toleriert CC-Indentation-Änderungen), restlicher Text literal. `re.fullmatch` stellt sicher dass nur der exakte Block (nicht CLAUDE.md-Kontext mit gleichem Preamble) matcht. Strip fließt in den bestehenden `_apply_final_sr_pass` (`stripped_all_sr`/`stripped_all_sr_msg0` mod). strip_vocab.py Rule `'ENV'` hinzugefügt: Marker `"As you answer the user's questions, you can use the following context:\n# userEmail"` — ermöglicht fn-Materialisierung via `attribute_chunk` für dual-log Attribution.
   - **6 strip_vocab.RULES Ergänzungen (2026-06-04):** Attribution-Coverage-Analyse (dev/proxy_dual_log/attribution_coverage.py) identifizierte 6 Kategorien die in Strip-Logs auftauchten aber keine RULES-Marker hatten → residual-gap. Jetzt behoben: `ENV` (new rule, `_apply_final_sr_pass`), `HP` (new rule, `stripped_hook_error_prefix`, `_apply_hook_prefix_strip`), `SN` (new rule, `_apply_final_sr_pass`), `FM` (new rule, marker ` was modified`, `_apply_final_sr_pass`), `UI`-Rule: secondary marker `IMPORTANT: After completing your current task` added (UI_PARTIAL-Strips), `CMD`-Rule: marker `The date has changed.` added (DATE_SR-Strips). Alle jetzt in `attribute_chunk` adressierbar.
   - `removed_plan_mode_sr`: weiterhin separat behandelt (text-block drop bei "Plan mode is active")
   - `trimmed_task_notification`: Strippt output-file/tool-use-id Tags aus task-notifications (non-failed TN) UND appended `_WAKEUP_TEXT` ans Content. Detection via `_top_level_content_contains` (payload_helpers.py) — prüft NUR top-level str/text-blocks, steigt NICHT in `tool_result`-Content ab. Verhindert false-positive wenn `<task-notification>` als DATA in einem tool_result auftaucht (z.B. RAG-Suchergebnis, grep-Dump, Code-Read).
   - `replaced_task_notification`: Ersetzt `<task-notification>` Blöcke mit `<status>failed</status>` durch `_WAKEUP_TEXT` (`'background done — check worker or other process\n'`). Gleiche `_top_level_content_contains`-Guard wie `trimmed_task_notification`.
   - `replaced_bg_completed_text` (`strip_bg_completed.py`): Ersetzt die erste CC-native BG-Exit-Notification (plain-text kill-signal format) durch `_WAKEUP_TEXT`. Weitere BG-Notifications werden gestrippt. Detection-Guard in `_apply_bg_exit_strip` (rules.py) ebenfalls via `_top_level_content_contains` — steigt nicht in `tool_result` ab. `_strip_bg_exit_notifications` traversiert nur noch `text`-Blöcke top-level, kein `tool_result`-Descent (defense in depth). Verhindert false-positive wenn `Background command "` als DATA in tool_result vorkommt.
   - **Wake-Up Dedup (commit `fcfe6c1`, 2026-05-22):** `_dedup_wakeup_blocks(messages)` läuft als finale Pass in `apply_modification_rules` nach allen anderen Modifications. Wenn `replaced_task_notification` UND `replaced_bg_completed_text` (oder `trimmed_task_notification` UND `replaced_bg_completed_text`) auf dieselbe User-Message gefeuert sind, sind beide unabhängig je einen `_WAKEUP_TEXT`-Block angehängt (TN-Pfad in `rules.py::_apply_first_pass`, BGK-Pfad in `strip_bg_completed.py`). Dedup kollabiert auf maximal 1 Wake-Up-Block pro Message (rstrip('\n')-vergleich behandelt beide Varianten — TN-Pfad mit `\n`, BGK-Pfad ohne — als denselben Signal). Touched nicht `stripped_msg_removed` (display invariant — wake-up wird nicht als gestripped angezeigt).
   - **BD Noise Strip (commit 384ced3, 2026-05-30):** `strip_bd_noise.py` entfernt alle informativen bd auto-import/export-Zeilen aus `tool_result`-Content: `auto-importing N bytes … into empty database`, `auto-imported N issues [and N memories] from …/.beads/issues.jsonl`, `auto-imported N issues into empty database`, `Exported N issues [and N memories] to …/.beads/issues.jsonl`, `auto-export: wrote … to …`, `auto-export: no changes since last export`, `auto-export: throttled (…)`, `auto-export: skipping[…]`, upgrade-recovery-Varianten. `Warning:`/`warning:`-prefixierte Fehlermeldungen (auto-export failed/skipped, auto-import: failed to parse) NICHT gestrippt. Handles `- `-Prefix der Import-Varianten via `^(?:- )?`. Fast-path `_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')` — drei Marker nötig weil `auto-imported N issues into empty database` keinen der ersten zwei enthält. Pass in `rules.py` nach `_apply_git_lock_strip`, mod-name `stripped_bd_noise`. strip_vocab.py Rule `'BD'` mit Markern `['issues.jsonl', 'auto-export: no changes', 'auto-export: throttled', 'auto-export: skipping']`.
   - **Git index.lock Advice Strip (commit a26f83a, 2026-05-30):** `strip_git_lock.py` entfernt den konstanten 5-Zeilen-git-Advice-Block (`"Another git process seems to be running in this repository…remove the file manually to continue."`) aus `tool_result`-Content. Block ist in git's `lockfile.c` hardcodiert — konstant über alle Repos/Versionen. Erhält die variable Zeile darüber (`Warning: auto-export: git add failed: … index.lock … File exists.`). Wired als `_apply_git_lock_strip`-Pass in `rules.py` nach `_apply_hook_prefix_strip`, mod-name `stripped_git_lock_advice`. Guard via `_content_contains` (steigt in tool_result ab). strip_vocab.py Rule `'GL'` mit Marker `'Another git process seems to be running'`.
   - `stripped_rejection_message`: Strippt rejection-Marker aus tool_result.content (eine der wenigen legitimen tool_result-strip-Operationen)
   - `replaced_system_prompt`: Ersetzt system[2] (>5000 chars) mit "." (Logging-Reduktion)
   - `stripped_sidecar_content` (commit 54d743e, 2026-04-23): Detektiert CC-interne Sidecar-Requests (single-msg plain-string payload, leere system, genau 1 user-msg mit plain-string content) und ersetzt `messages[0].content` durch einen kurzen Marker `[SIDECAR_STRIPPED_<n>_BYTES]`. Short-circuit early in `apply_modification_rules` um spurious `stripped_all_sr_msg0` auf dem Marker zu vermeiden. Evidence: session 1776956156 REQ#80.1 hatte 49,586c Inhalt und ~24k CC tokens allein für den Sidecar-Injection.

2. `_strip_all_cache_control()` — Entfernt ALLE cache_control Marker von Claude Code:
   - system blocks, tools, messages (top-level + content blocks)
   - Ruft danach `_normalize_user_content_shape()` auf: User-Messages deren Content nach dem Strip `[{"type":"text","text":"X"}]` ist (single text block, exakt `{type,text}` Keys) werden auf plain string `"X"` kollabiert. Hintergrund: CC sendet User-Msgs nativ als String wenn keine BP drauf liegt, als list-with-block wenn BP drauf ist. Ohne Normalisierung gibt das Byte-Diff zwischen Requests wenn BP4 von einer Msg wegzieht. Siehe `cache_rebuild_cases.md` Case 1 (2026-04-12, commit 0f847b0).

3. `_set_cache_breakpoints()` — Setzt eigene Breakpoints (max 4) auf modifiziertem Payload. **BP Layout v3 (2026-04-16, commit dcb6aea + merge):**
   - **BP1 — system[2] (neu):** `cache_control` direkt auf dem `system[2]` Text-Block. Prefix endet bei sys[2] → sys[3] (CC-injected env: cwd, gitStatus, Recent commits) liegt NICHT im Prefix → Cross-Session-Hit überlebt sys[3]-Drift (Commits, Main↔Worker cwd-Unterschied). Verifiziert: Fresh Session REQ#1 CR=61,231 / CC=0 bei byte-identischem sys[3] zwischen Sessions (2026-04-16).
   - **BP2 — Tools End:** Letztes Tool OHNE `defer_loading` (defer_loading + cache_control = API Error). Cacht gesamten tools-Block.
   - **BP3 — Messages last_unchanged:** Letzte Message die sich gegenüber dem vorigen Request NICHT geändert hat (`first_diff_index - 1` auf modifiziertem Content).
   - **BP4 — Messages last:** Letzte Message, letzter Content-Block — für nächsten Request.
   - **Entfernt (BP Layout v2 → v3):** Tools-Anchor bei Tool-Growth. Tools werden in der Praxis innerhalb einer Session nicht verändert, der Anchor war selten aktiv. Slot freigemacht für sys[2]-Marker. `prev_tools_count_by_model` State in `addon.py` komplett entfernt.

### Context Editing (ab 2026-04-17)

`_inject_context_management(payload)` in `src/proxy/inject_helpers.py` injiziert einen `context_management`-Block in den API-Payload, wenn in `~/.claude/shared-rules/proxy_rules.json` unter `context_management.enabled: true` gesetzt.

Injizierter Block:
```json
{
  "context_management": {
    "edits": [
      {
        "type": "clear_tool_uses_20250919",
        "trigger": {"type": "input_tokens", "value": 100000},
        "keep":    {"type": "tool_uses",    "value": 5},
        "clear_at_least": {"type": "input_tokens", "value": 10000}
      },
      {
        "type": "clear_thinking_20251015",
        "keep": {"type": "thinking_turns", "value": 2}
      }
    ]
  }
}
```

**Strategie `clear_tool_uses_20250919`:** Löscht alte Tool-Result-Content server-seitig sobald > 100k Input-Tokens akkumuliert sind. Behält die letzten 5 Tool-Uses. Mindest-Löschmenge 10k Tokens pro Clearing-Event (sichert, dass der Cache-Invalidierungs-Overhead sich lohnt).

**Strategie `clear_thinking_20251015`:** Löscht alte Thinking-Blöcke, behält nur die letzten 2 Thinking-Turns.

**Beta-Header:** Keine Manipulation. CC's `anthropic-beta`-Header passiert den Proxy unverändert. Die frühere Logik (Strip `interleaved-thinking-2025-05-14`, Add `context-management-2025-06-27`) wurde entfernt — Rationale, vollständige Flag-Analyse (14 Flags) und Verdict in `decisions/OldThemes/proxy_header_mods.md` (Research Result resolved).

**Logging:** `entry["context_management_injected"]: bool` in jedem Proxy-Log-Entry. `"injected_context_management"` in `modifications`-Liste wenn angewendet.

**Cache-Interaktion:** Laut API-Docs invalidiert Tool-Result-Clearing den Cached-Prompt-Prefix sobald Content gelöscht wird. `clear_at_least: 10000` stellt sicher, dass mindestens 10k Tokens pro Event gelöscht werden — macht den Invalidierungs-Overhead amortisierbar. Trigger bei 100k Input-Tokens ist konservativ: kurze Sessions (<100k) sind vollständig unberührt.

**Konfiguration:**
```json
// ~/.claude/shared-rules/proxy_rules.json
{
  "context_management": {
    "enabled": true,
    "clear_tool_uses": {"enabled": true, "trigger_input_tokens": 100000, "keep_tool_uses": 5, "clear_at_least_tokens": 10000},
    "clear_thinking": {"enabled": true, "keep_thinking_turns": 2}
  }
}
```

### Projekt-Rules in sys[2] (ab Refactor proj-rules-to-sys2, 2026-04-16)

`_load_system2_rules(model_family, project_path)` lädt seit diesem Refactor drei Schichten:

1. **global** — `system2_rules.global.files` (immer, ausser exclude_projects)
2. **model** — `system2_rules.opus.files` oder `system2_rules.worker.files`
3. **project** — `system2_rules.projects.<name>.files` wenn `path_contains in project_path`

Verkettung: `"\n\n".join(parts)` — deterministische Reihenfolge global → model → project. Resultat landet in `system[2]`, das durch BP1 gecacht wird.

`msg[0]` enthält nach diesem Refactor **nur noch user-input**: Als letzter Pass in `apply_modification_rules` werden via `_strip_all_system_reminders()` alle verbleibenden `<system-reminder>…</system-reminder>` Blöcke aus `messages[0]` entfernt (sofern `role == "user"`). Modifier: `"stripped_all_sr_msg0"`.

**Erwarteter Cross-Session Cache-Effekt:** 2. Fresh-Session innerhalb TTL (55min): CR ≥ 55k / CC ≤ 3k (vs. pre-refactor CR=41k / CC=20k). Grund: Projekt-Rules liegen jetzt im sys[2]-Prefix der BP1-Cache-Region und werden cross-session gecacht, statt session-spezifisch in msg[0] zu driften.

### State-Tracking

`self.prev_messages_by_model` speichert Message-Summaries des **modifizierten** Payloads (nicht Original). Getrennt nach model_family ("opus" / "haiku"). BP3-Berechnung vergleicht aktuelle modifizierte Messages mit vorherigen modifizierten Messages via `_compute_diff()`.

### Worker-Isolation

Jeder Worker in einem Worktree bekommt einen eigenen mitmproxy-Prozess auf eigenem Port mit eigener Log-Datei. Implementiert in `tmux_spawn.sh` (iterative-dev Plugin):
- Worker erkennt Proxy via `/tmp/.monitor_cc_proxy_<session_hash>`
- Hash basiert auf Projekt-Pfad (Worktree-Suffix wird gestrippt → gleicher Hash wie Main)
- Eigener Port (nächster freier ab Main-Port + 1)
- Eigene Log-Datei: `api_requests_<worker_session_id>.jsonl`
- Cross-Project-Worker (anderes Projekt als Main) bekommen keinen Proxy — Marker existiert nur für das Main-Projekt

### count_tokens Passthrough

`_is_messages_request()` in `src/proxy/addon.py` matched per 2026-05-29 exakt auf `/v1/messages` + optionalen Query-String:
```python
path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?")
```
Zuvor: `path.startswith(MESSAGES_PATH)` — matcht auch `/v1/messages/count_tokens?beta=true` → `_inject_model_override` injizierte `max_tokens` → API 400. Jetzt: count_tokens-Requests laufen KOMPLETT unmodifiziert durch. Kein Stripping, kein Inject, kein Log-Entry in `api_requests_*.jsonl`.

### Model Override

`_inject_model_override(payload, model_family)` in `src/proxy/inject_helpers.py` injects `model`, `effort`, `max_tokens`, and `thinking` from `~/.claude/shared-rules/proxy_rules.json` blocks `model_override` (main/opus) and `model_override_worker` (sonnet).

| Param | Opus (`model_override`) | Worker (`model_override_worker`) |
|---|---|---|
| `model` | `claude-opus-4-8` | `claude-sonnet-4-6` |
| `effort` | `xhigh` | `high` |
| `max_tokens` | `128000` | `64000` |
| `thinking` | adaptive + omitted | adaptive + omitted |

Guard: `_is_messages_request()` in `addon.py` restricts injection to exact `/v1/messages` path (+ optional query string) — count_tokens requests pass through unmodified (see `### count_tokens Passthrough`). Value `64000` reflects current `proxy_rules.json` after correction from 128000 (Sonnet 4.6 ceiling; see `decisions/OldThemes/model_override_limits.md`).

### 4xx Error Logging

`ProxyAddon.response()` schreibt 4xx-Fehler als einzelne JSONL-Zeile in `src/logs/api_errors.jsonl` (rollend, 7-Tage-Retention via `cleanup_old_jsonl`). Felder: `ts`, `status_code`, `error_response`, `request_url`, `request_payload`. Davor: eine Einzeldatei `api_error_payload_<ts>.json` pro Fehler.

### Log Pipeline

```
Main Session → mitmdump :8084 → proxy_addon.py → api_requests_opus_<project>_<timestamp>.jsonl
Worker (Worktree) → mitmdump :8085 → proxy_addon.py → api_requests_worker_<name>_<timestamp>.jsonl
4xx Errors (beide) → api_errors.jsonl (rollend, 7d-Retention)
```

Alle schreiben nach `$MONITOR_CC_ROOT/src/logs/`. Monitor liest per `session_id` das richtige Log.

Zusätzlich schreibt `addon.py` sechs additive Logs in `src/logs/dual_log/` (Subfolder, auto-created):
- `api_requests_<log_id>_original.jsonl` — roher CC-Payload VOR jeder Modifikation (`payload` vor `apply_modification_rules`). Voll-kumulativ, jeder Request vollständig. `model` = CC-angefordertes Modell vor Override.
- `api_requests_<log_id>_forwarded.jsonl` — **Delta-Log** (`type: forwarded_delta`). REQ#1 voll (`is_first: true`), ab REQ#2 nur geänderte/neue Elemente per per-Element-Content-Hash-Diff (system/tools/messages getrennt). Hash-Vergleich normalisiert zweistufig: (1) `cache_control` rekursiv strippen (`_strip_cache_control`) → BP3/BP4-Wanderung kein Spurious-Delta; (2) Message-Shape normalisieren (`_normalize_msg_shape_for_hash`) — single-text-block-Liste `[{type,text}]` → plain String, spiegelt `cache._normalize_user_content_shape` exakt → BP-induzierter Form-Flip erzeugt kein Spurious-Delta. Geschriebener Inhalt behält Marker und echte Form. self-healing Hash-Kette: `prev_delta_hashes_by_model` wird erst nach erfolgreichem Write aktualisiert. Entry-Felder: `type`, `request_id`, `timestamp`, `model` (post-Override), `is_first`, `counts` (Gesamtzahl system/tools/messages), `system_delta`/`tools_delta`/`messages_delta` (nur geänderte/neue Indizes als Dict), `anthropic_beta` (vollständige Liste der CC-Beta-Feature-Flags aus dem HTTP-Request-Header `anthropic-beta`, leer falls Header absent), `context_management` (body-field passthrough, None falls absent), `diagnostics` (body-field passthrough, None falls absent). `model` = ggf. überschriebener Wert nach `_inject_model_override`.
- `api_requests_<log_id>_stripped.jsonl` — **Delta-Log** (`type: stripped_delta`). Was der Proxy aus dem original Payload ENTFERNT hat (in original, nicht in forwarded). Geschrieben in `response()`-Hook nach dem upstream-Send (zero forwarding latency). Diff via `_build_stripped_injected_deltas` (in `logging.py`) + `diff_engine.py`-Engine; beide Payloads werden vor dem Diff via `_strip_cache_control` normalisiert → BP-Repositionierung erzeugt kein Spurious-Strip; User-Messages zusätzlich via `_normalize_msg_shape_for_hash` normalisiert → json_reserialization-False-Positives (string vs. block-list durch `_set_cache_breakpoints`) eliminiert. Vollständiger Payload-Diff: deckt system/tools/messages UND alle Top-Level-Felder (`_diff_top_level_fields`) ab — der model-Override erscheint korrekt als `fields_delta["model"]`. Delta-Encoding: per-location hash-chain (`loc_key → MD5[:10]` der Span-Texte via `_hash_spans`), state in `prev_stripped_hashes_by_model` (keyed by model_family). Stabile Strips (sys[2] identische Rules) erscheinen nur im ersten Request. **fn_map (neu):** Top-Level-Dict `{loc_key → fn_name}` — verantwortliche Funktion pro Strip-Entry, AT WRITE TIME via `_attribute_chunk` (messages), `_SYS_FN`/`_FIELD_STRIP_FN`/tool-shape (andere Sektionen). Alte Entries ohne fn_map sind read-side-safe (Feld einfach absent).
- `api_requests_<log_id>_injected.jsonl` — **Delta-Log** (`type: injected_delta`). Was der Proxy in den forwarded Payload HINZUGEFÜGT hat (in forwarded, nicht in original). State in `prev_injected_hashes_by_model`. `fields_delta["model"]` enthält das Override-Zielmodell. Logisch nicht-redundant zu original/forwarded: die Klassifikation "dies wurde injiziert" ist nirgends sonst persistiert. **Span-Format (Stage 1):** `system_delta[idx]`, `messages_delta[midx][bidx]`, `tools_delta[name]["desc"]` speichern geordnete Span-Listen `[[tag, text], ...]` mit Tags `"equal"` / `"injected"` (statt flacher Textlisten). Nur Blöcke mit ≥1 `injected`-Span werden geschrieben. Equal-Spans = Kontext-Anker (Inline-Render: equal=DIM, injected=DIM_GREEN_BG). Hash via `_hash_span_sequence()` (Namespace-Key `tag:text|...`). `fields_delta` und `tools_delta[name]["whole"]` unverändert. Backward-compat: old-format-Entries (item[0] = str) vs new-format (item[0] = list) per `isinstance(val[0], (list, tuple))`. **fn_map (neu):** wie stripped; inject-side messages via `"background done"` check (→ `_apply_bg_exit_strip`) oder `_attribute_chunk` fallback; fields via `_FIELD_INJECT_FN` (inkl. `context_management → _inject_context_management`).
- `api_requests_<log_id>_errors.jsonl` — Derived tool-error log. `is_error=True` tool_result blocks aus dem Original-Payload, dedup by `tool_use_id` per model_family, geschrieben im `request()`-Hook. Format: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}`.
- `api_requests_<log_id>_response.jsonl` — Response-HTTP-Header-Log. Geschrieben im `responseheaders()`-Hook für ALLE Status-Codes (kein 2xx-Gate — 429 `retry-after` muss erfasst werden). Gefiltert via `_filter_response_headers` (exact: `request-id`, `retry-after`, `anthropic-organization-id`; prefix-match: `anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`; Keys normalisiert zu lowercase). Entry-Felder: `flow_id`, `timestamp`, `request_id` (aus Response-Header `request-id`), `status_code`, `headers` (gefiltertes Dict). Korrelation zu allen anderen Logs via `flow_id`. Writer-Handle: `self.response_log_file = _resolve_dual_log_file("response")`.

Alle sechs Writes je in eigenem `try/except` — Fehler beeinflussen nie Forwarding oder Main-Log. `_stripped`/`_injected` werden vom `response()`-Hook geschrieben (Metadata-Bridge: `mc_original_payload`, `mc_modified_payload`, `mc_model_family` auf `flow.metadata`). Janitor-Rotation: alle `dual_log/`-Files einer log_id werden suffix-aligned gemeinsam rotiert — nach der Haupt-Log-Rotation (count-30 opus/worker) werden alle `dual_log/api_requests_*.jsonl` ohne passende `log_id` gelöscht. Implementiert in `_janitor_cleanup_jsonl_logs()` (`claude_proxy_start.sh`); alle sechs Suffixe in `_LOG_REGISTRY` (`log_janitor.py`) mit `retention="count-30"`, `janitor_trigger="proxy-start-bash"`.

**Korrelations-Key:** Alle sechs Dual-Log-Entries tragen `"flow_id": flow.id` — mitmproxys stabiles Per-Flow-UUID, das über alle Hooks identisch ist. `request_id` in `_response` kommt aus dem Anthropic-Response-Header `request-id` (direkt verfügbar in `responseheaders()`). `flow_id` ist der Read-Side-Join-Key für alle sechs Logs.

### Tool Stripping (TOOL_BLOCKLIST)

`TOOL_BLOCKLIST` (frozenset) in `proxy_addon.py` entfernt 21 ungenutzte Tools aus dem `tools`-Array vor dem API-Send. ~25k chars weniger pro Request. Agent-Tool bleibt, aber Description getrimmt auf git-committer-only (~300 chars statt 10k).

### Live-Copy Isolation

`claude_proxy_start.sh` kopiert `proxy_addon.py` nach `$LOG_DIR/.proxy_addon_live.py` beim Start. mitmproxy lädt die Kopie. Git-Merges auf das Original triggern keinen Hot-Reload. Cleanup bei Proxy-Stop.

### Log-Naming & Rotation

Log-Dateien: `api_requests_{projektname}_{timestamp}.jsonl` statt kryptischer MD5-Hashes. Max 30 Dateien, älteste werden bei Proxy-Start gelöscht.

### Prefix-Hash Instrumentation (ab Commit feat/prefix-hash-instrumentation)

`_build_sent_meta` (seit Refactor 2026-04-19 in `src/proxy/hash_meta.py`, aufgerufen aus `addon.py`) schreibt vier zusätzliche Felder pro `sent_meta`-Entry:

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

**Was NICHT fixiert wird:**
- sys[0], sys[1], sys[3] — Claude Code kontrolliert, unberührt
- messages[1..N-1] — session-volatil per Design
- tools[] — append-only, unberührt

**Implementierung:** Orchestrierung in `addon.py`, Helfer `_capture_fixation` / `_apply_fixation` seit Refactor 2026-04-19 in `src/proxy/fixation.py`. Keine Änderung an `rules.py`. Nach `apply_modification_rules()` wird entweder gecaptured (erster Request) oder via `_apply_fixation()` überschrieben (Folge-Requests). `apply_modification_rules()` läuft immer vollständig durch (kein Short-Circuit) — der Overhead ist minimal (mtime-basiertes File-Caching in `_read_rule_file()`), die Bytes werden danach überschrieben.

**Edge Cases:**
- Content `"."` (nach stripping geleerte Messages) — kein `</system-reminder>` Marker, `_capture_fixation` speichert nichts, `_apply_fixation` ändert nichts, kein Crash.
- Haiku (model_family="haiku") — `_load_system2_rules` gibt `""` zurück → sys[2] wird `"."`. Auch für Haiku wird fixated gespeichert (mit `"."`) damit der zweite Request nicht durch Datei-mtime-Änderungen abweicht.

### API Constraints (Referenz)

- Max 4 Breakpoints pro Request
- `defer_loading=true` und `cache_control` auf dem gleichen Tool = API Error
- Min cacheable prefix: 2048 Tokens (Opus) / 1024 (Haiku)
- Cache Write kostet 125% der Token — falsches Placement kann teurer sein als kein Caching
- `cache_control` marker: `{"type": "ephemeral"}` (kein TTL nötig, API bestimmt)
- `scope: "global"` — Content-basierter Cache über Sessions/API-Keys hinweg. Gleicher Content = Cache-Hit, unterschiedlicher Content = separate Einträge. Kein Cross-Contamination zwischen Opus und Worker.

### Tool Injection

Before this change: `tools[]` fully controlled by Claude Code. MCP schemas loaded lazily via ToolSearch (alphabetical insert into the middle of the tools array). Deferred built-ins (CronList, ListMcpResourcesTool etc.) appear mid-session via CC's deferred-tool lifecycle. Both mechanisms cause mid-session `tools[]` mutations that break the byte prefix before BP2 → cache rebuilds (see `cache_rebuild_cases.md` Case 4 Tool INSERT subsection).

Current implementation: Proxy takes full deterministic control of `tools[]`:
- `ToolSearch`, `ScheduleWakeup`, `Monitor` added to `TOOL_BLOCKLIST` → stripped from every request
- CC deferred built-ins already in blocklist (TaskCreate, CronCreate, AskUserQuestion etc.)
- `src/proxy/tool_injection.py` injects MCP schemas: iterative-dev always from REQ#1, other plugins appended when activated via `activate_plugin` MCP tool (iterative-dev/blank server.py)
- Schema store at `src/proxy/schemas/<plugin>/<tool>.json` populated by `dev/tool_injection/01_extract_schemas.py` — one-time extraction via FastMCP introspection per plugin
- Append-only injection logic: iterative-dev first, active plugins in activation order, stable alphabetical within each plugin block
- `active_plugins` tracked in `ProxyAddon.fixated` for session-stable behavior; explicit `activate_plugin` calls emit `"active_plugins_changed"` modifier (one-time controlled rebuild by design)

**Update 2026-04-14 (evening) — Research Plugins Converted to Skill+CLI:**

Scope of tool injection **narrowed**: on 2026-04-14 the 4 research plugins `github-research`, `reddit`, `arxiv`, `rag` were converted from MCP servers to pure Skill+CLI plugins (43 tool schemas removed from API prefix). Each got a `cli.py` entry point; `server.py` + `mcp-start.sh` deleted; `plugin.json` `mcpServers` block removed.

Consequences for Tool Injection:
- `tool_injection.py` now only handles `iterative-dev` (4 tools) — the only remaining MCP plugin
- `active_plugins.json` effectively stable at `{"plugins":["iterative-dev"]}` — no activation flow for research plugins because they have no MCP tools to inject
- Dynamic `activate_plugin` MCP tool becomes an edge case (still exists for theoretical future MCP plugins)
- First Opus REQ tools count: 7 built-ins + 4 iterative-dev = **11** (previously 31+ with research plugins injected)
- Schema bytes per request: ~2k (previously ~13k)
- Research plugin tools are now invoked via `Bash(<plugin>/.venv/bin/python <plugin>/cli.py <cmd> ...)` — zero prefix cost, documented in each plugin's SKILL.md

Affected commits (per repo):
- `github-research` v1.1.0 — commit `37807a3`
- `reddit` v1.1.0 — commit `381f97e`
- `arxiv` v1.1.0 — commit `8b89e08`
- `rag` v1.1.0 — commit `909375d`

### Pane RAM (Phase 2a abgeschlossen 2026-04-29)

Vier Hebel implementiert + gemerged auf dev:

**(1) Lazy-msg-strip + lazy-reload (commit cf8037c, 2026-04-29).** `src/proxy_display/parser.py` stempelt `entry['_byte_offset']` per Zeile beim Parse. `_lazy_load_messages(entry, log_path)` re-populiert `entry['messages']` on-demand via `seek(offset) + readline()`. Pane-Module (proxy, worker_proxy) droppen nach jedem `extend()` die `messages`-Liste aus Entries die NICHT in den letzten 10 sind UND NICHT aktiv expanded — `_strip_inactive_messages()` checkt drei expand-key forms (`entry_idx`, `('req', N)`, `(N, 'neg_delta')`). Click-handler triggert `_lazy_load_messages` für entry + prev_same beim Expand. Das löst das O(N²)-Wachstum durch kumulative Anthropic-Wire-Format Messages. Konstante: `PROXY_MESSAGES_KEEP_LAST = 10` in `src/constants.py`.

**(2) tracemalloc env-var-Gate (commit 10f110a, 2026-04-29).** `src/ram_audit/instrument.py` aktiviert `tracemalloc.start(25)` nur wenn `MONITOR_CC_RAM_AUDIT=1` gesetzt ist. Default off → kein 2-5x CPU-Overhead pro Python-Allokation in der proxy-pane Render-Schleife. Lag/Flicker im proxy-pane war primär dadurch verursacht.

**(3) Warnings tail-bytes (commits 2ffe9b9 + 166b18b + 47a4415, 2026-04-29).** `src/panes/warnings_pane.py` setzt im Site-A-Reset-Block `_proxy_log_position = max(0, fsize - WARNINGS_INITIAL_TAIL_BYTES)` statt 0. `WARNINGS_INITIAL_TAIL_BYTES = 50_000_000` in constants.py. `scan_worker_logs` in parser.py akzeptiert zwei Parameter: `tail_bytes` (für first-time-seen worker logs) und `min_mtime` (skip worker logs mit mtime < `_monitor_start_ts`). Damit parst warnings nur die letzten 50 MB der main proxy log + frische worker logs aus der laufenden Session — alte Worker-Logs aus früheren Sessions werden komplett geskipped.

**(4) Subprocess-parse für Initial-Parse (commit c3d69ed, 2026-04-29).** `_parse_log_file_isolated` und `parse_proxy_log_isolated` in `src/proxy_display/parser.py` spawnen für `last_position == 0` einen Child-Prozess via `multiprocessing.get_context('spawn')`. `_subprocess_worker` parst im Child, droppt messages pre-IPC, sendet entries + new_position + pending_rids via Queue. Parent rebuildet pending_by_rid via RID-Set-Lookup (nicht via Pickle-Kopien). Child-Exit gibt alle Pages ans OS zurück → der ~3 GB Initial-Parse-Peak hängt nicht mehr im Parent-Prozess. Fallback bei Crash, Timeout (default 60s, `SUBPROCESS_PARSE_TIMEOUT` env-überridden), oder IPC-Pickle-Failure auf in-parent Parse. Aktive Caller-Sites: `pane.py`, `worker_proxy_pane.py`.

## Evidenz

### Cache-Rebuild Analysis (Session a3b6577a)

Script: `dev/session_analysis/04_cache_validation.py` (stdout-only, kein persistent Report-MD). Dataset: Proxy-Log `src/logs/api_requests_f93afc17.jsonl` (825MB, 2026-04-08) + Session-JSONL `a3b6577a-8f2c-4cef-a594-15aa18c0f520.jsonl`. 148 Requests mit Modifications:

- **98%** der Requests hatten Modifications VOR dem Breakpoint
- 4 Cache-Rebuilds: REQ#0 36k CC (erwartet), REQ#1 27k CC (ToolSearch), REQ#70 93k CC / 9k CR (91% Rebuild), REQ#133 162k CC / 9k CR (95% Rebuild)
- 9,297 CR bei REQ#70 + #133 = exakt `system[2]` Breakpoint — alles danach (Tools + 100+ Messages) neu geschrieben
- Gesamtkosten: 319k Tokens für Rebuilds (2% vom Total, 162k = ~6% Session-Limit für einen Request)

**Kritisch:** Proxy-Modifications ändern Messages die VOR dem cache_control Breakpoint liegen. Die API sieht modifizierten Content → Prefix-Mismatch → Cache invalidiert.

### Fix-Verifikation

Script: `dev/session_analysis/04_cache_validation.py` / `02_cache_timeline.py` (stdout-only, kein persistent Report-MD). Dataset: Test-Project-Session (14+ Requests):

- REQ#2: CR:0, CC:30.478 (erster Request, erwartet)
- REQ#3–#14: Alle CR >30k, CC nur 150–1200 (neuer Content)
- **Kein einziger Rebuild** — auch nicht bei ToolSearch (REQ#8: CC:425)
- BP3 verhindert Cache-Invalidierung: modifizierter Content ist deterministisch → Prefix zwischen Requests stabil

### Tool Injection Evidenz

Script: `dev/session_analysis/04_cache_validation.py` (stdout-only). Dataset: `api_requests_opus_monitor_cc_1776099723.jsonl`: REQ#2 → REQ#3 Rebuild als Folge von Tool INSERT (ToolSearch-Load). Detailliert in `decisions/cache_rebuild_cases.md` Case 4 (Tool INSERT subsection).

Stage 3 live verification — pending next session.

### Pane RAM KPIs (29.04)

Script: `dev/ram_audit/dump_all.sh` (SIGUSR1 → pro Pane-PID-Datei, Format dokumentiert in `dev/ram_audit/DOCS.md`). Dataset: "final dump_all post-restart 2026-04-29". Dumps unter `dev/ram_audit/dumps/` (gitignored):

| Pane | Baseline 28.04 | Final 29.04 | Reduktion |
|---|---|---|---|
| proxy | 1,151 MB | 504 MB | -56% |
| worker_proxy | 385 MB | 170 MB | -56% |
| metadata | 1,304 MB | 465 MB | -64% |
| worker_metadata | 370 MB | 156 MB | -58% |
| main | 1,131 MB | 1,043 MB | -8% (out-of-scope) |
| warnings | 2,856 MB | 690 MB | -76% |
| **Total** | **7,497 MB** | **3,208 MB** | **-57%** |

Subjektiv: Lag/Flicker im proxy-pane vollständig weg (Quelle war tracemalloc-Overhead, nicht RAM). RSS warnings 2,856 → 506 MB (-82%) live verifiziert nach Hebel 3.

### Tokenizer Approximation (chars/token)

`dev/session_analysis/04_reports/20260416_222700_token_ratios.md` (Script: `dev/session_analysis/06_char_token_ratio.py`, Proxy-Log: `api_requests_opus_monitor_cc_1776359177.jsonl`, Session: `48273804-df12-42e1-bd5f-dd64fe734f48.jsonl`, 2026-04-16):

- Known prefix anchor: **154,550 chars → 41,975 tokens = 3.68 chars/token**
- Full-rebuild ratio (CR=0): 3.42 chars/token (N=0 in dieser Session; N=3 über mehrere historische Sessions, stddev 0.11)
- 84 message-delta data-points; median 0.53 chars/token (delta-only, nicht für Prefix-Kalkulation nutzbar)
- Stabil ~3.4–3.7 über Sessions ohne interleaved thinking

**tiktoken cl100k_base ist unbrauchbar** — unterschätzt Claude's Tokenisierung um 35–75% (variabel mit thinking-Anteil). Nicht für Proxy-Entscheidungen verwenden.

**Caveat:** Pro-Segment-Ratios (sys vs tools vs messages separat) sind mit aktuellen Daten NICHT extrahierbar (sys/tools konstant pro Session = keine Varianz für Regression). Der 3.68-Wert ist Prefix-dominiert (sys+tools machen 95% des Payloads aus) und gilt als "good enough" Gesamtapproximation.

Details + Experimente + Paths-Forward: `decisions/OldThemes/tokenizer/tokenizer_baseline.md` (geparkt).

### Model Override Limits

Per-model max output (synchronous Messages API):

| Model | Max output |
|---|---|
| Opus 4.8 | 128,000 |
| Sonnet 4.6 | 64,000 |
| Haiku 4.5 | 64,000 |

Source: `monitor-cc-reference`: `about_claude_models_overview.md` (Max output row), `extended_thinking.md`. Note: 300k is Batches-API-only (`output-300k-2026-03-24`).

`max_tokens` schema (`monitor-cc-reference`: `api_messages_create.md`): `minimum: 0`, no max enforced; `stop_reason: "max_tokens"` = "exceeded requested `max_tokens` or the model's maximum" → API clamps to ceiling. Evidence: Sonnet workers ran `max_tokens=128000`, zero 400s; schema enforces no upper bound. Caveat: "clamp" inferred from stop_reason wording + no-400; docs contain no literal clamp statement.

Effort levels (`monitor-cc-reference`: `effort.md`): `low < medium < high < xhigh < max`. `high` = "exactly the same behavior as omitting the effort parameter". `xhigh` Opus 4.8 / 4.7 ONLY. Sonnet ceiling = `max`; Sonnet recommended default = `medium`. No beta header required for effort param.

Full investigation trail: `decisions/OldThemes/model_override_limits.md`.

## Recommendation (SOLL)

Keep (no change needed) — eigene Breakpoints sind implementiert und verifiziert. TTL `1h` und `scope: "global"` korrekt auf Markern gesetzt.

### Global Rules Caching

Change: Hook-injizierte Rules (78k chars, `SessionStart hook additional context:`) werden aus MSG[0] extrahiert und als eigener System-Block mit `scope: "global"` eingefügt. System-Block Position: nach system[2] (stripped), vor dynamischem Content (gitStatus). BP1 zielt auf den Rules-Block statt auf den letzten System-Block.

Erwarteter Impact: ~25-30k Tokens CR statt CC ab dem 2. Request jeder Session. Cross-session Cache-Hits bei unveränderten Rules. Cross-model: Opus + Worker mit gleichen Rules → Cache-Hit.

### Rejection Message Stripping

Change: ESC-Abbruch tool_result Messages ("The user doesn't want to proceed with this tool use...") werden auf `"."` gekürzt. Marker: `_REJECTION_MARKER` Konstante.

### Agent-Tool Trimming

Change: Agent-Tool bleibt im tools-Array, aber Description von ~10k auf ~300 chars getrimmt (nur git-committer Subagent-Type).

### Session-Guidance Stripping

Change: `# Session-specific guidance` Sektion aus system[3→4] entfernt. `# Environment`, `# Language`, `gitStatus` bleiben erhalten.

### Worker Proxy Live-Copy

Change: Worker-Proxies verwenden jetzt ebenfalls Live-Copy (`.proxy_addon_worker_{name}.py`). Verhindert Hot-Reload bei Git-Merges auf proxy_addon.py. Fix in iterative-dev Plugin `tmux_spawn.sh`.

### Proxy Log-Naming

Change: Main-Logs heißen `api_requests_opus_{project}_{timestamp}.jsonl`, Worker-Logs `api_requests_worker_{name}_{timestamp}.jsonl`. Klare Trennung zwischen Opus und Worker Proxy-Logs.

### Tool Injection (Deterministic Control)

Change: Proxy takes full deterministic control of `tools[]`:
- `ToolSearch`, `ScheduleWakeup`, `Monitor` added to `TOOL_BLOCKLIST` → stripped from every request
- CC deferred built-ins already in blocklist (TaskCreate, CronCreate, AskUserQuestion etc.)
- `src/proxy/tool_injection.py` injects MCP schemas: iterative-dev always from REQ#1, other plugins appended when activated via `activate_plugin` MCP tool
- Schema store at `src/proxy/schemas/<plugin>/<tool>.json` populated by `dev/tool_injection/01_extract_schemas.py` — one-time extraction via FastMCP introspection per plugin
- Append-only injection logic: iterative-dev first, active plugins in activation order, stable alphabetical within each plugin block
- `active_plugins` tracked in `ProxyAddon.fixated` for session-stable behavior

### Model Override — max_tokens

Change applied: worker `max_tokens` 128000 → 64000 (Sonnet 4.6 ceiling). Opus 128000 kept (= Opus 4.8 ceiling, exact). Source: `monitor-cc-reference` `about_claude_models_overview.md`.

### Model Override — effort

Keep: worker `high`, opus `xhigh`. No change. `high` = default (deliberate); `xhigh` valid on Opus 4.8 only — must NOT be set on Sonnet.

### anthropic-beta Headers

Keep: ALL 14 flags pass-through unmodified, no manipulation. Per-flag research resolved in `decisions/OldThemes/proxy_header_mods.md`. Conclusion: no flag worth stripping — each is auth-critical, feature-active, cost-relevant, or correctness-sensitive.

## Offene Fragen

- Langzeit-Stabilität: Verhalten bei Sessions >500 Requests noch nicht beobachtet
- Claude Code Updates könnten cache_control Handling ändern (z.B. mehr als 2 eigene Breakpoints) — `_strip_all_cache_control` entfernt alles, daher robust gegen Änderungen
- Global Rules Caching: `scope: "global"` auf eigenen System-Blöcken verifizieren — cross-session Cache-Hit testen (gleiche Rules, neue Session → CR statt CC?)
- Whether CC dispatches `tool_use` calls for proxy-injected MCP tools whose MCP client is still connected but which were never client-side loaded via ToolSearch. Stage 0 (hardcoded bead_list) already passed in a prior session; Stage 3 tests this for the full iterative-dev schema set and github-research via `activate_plugin`.
- `claude_proxy_start.sh` integration: schema store currently populated manually via `01_extract_schemas.py`. Next step is to run the extractor automatically in the proxy startup script.
- **main-pane bei 1043 MB** — größter verbleibender Verbraucher. Liegt nicht an proxy_display-Pfad sondern an `core/monitor.py` das session-JSONLs aus `~/.claude/projects/**/*.jsonl` parst (eigener code-pfad). Folge: subprocess-parse-Pattern für session-JSONL parsing analog zur vu0n-Lösung.
- **Periodic Pane-Respawn / pymalloc-Akkumulation** — subprocess-parse löst nur den Initial-Peak im Parent. Ongoing inkrementelle Allokationen akkumulieren pymalloc-Pages über Stunden. Beobachtet: proxy 506 → 624 → 749 MB binnen Stunden. Folge: periodischer pane-self-respawn ODER subprocess-pattern auch für inkrementelle Parses.

## Quellen

- Anthropic API Docs: Prompt Caching (cache_control Semantik, Breakpoint-Limits)
- `cache_rebuild_cases.md` Case 4 (Tool INSERT subsection)
