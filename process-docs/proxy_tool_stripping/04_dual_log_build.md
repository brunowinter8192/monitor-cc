# Dual-Log Build — Additive Baseline Logging

Build step 2026-06-02. First concrete iteration of the architecture from `03_logging_redesign.md`.
Rein additives Logging — keine Monitor-Leseseite, keine Janitor-Änderungen, keine Proxy-Logik-Änderungen.

## Was gebaut wurde

**Einzige geänderte Datei:** `src/proxy/addon.py`

Zwei neue, vollständig additive JSONL-Writes in `ProxyAddon.request()`, je in eigenem `try/except` isoliert.
Schreibfehler propagieren nie zur Request-Forwarding-Logik oder den bestehenden Logs.

**Helper:** `_resolve_dual_log_file(suffix: str) -> Path` — spiegelt `_resolve_log_file()`, schreibt in
`$MONITOR_CC_ROOT/src/logs/dual_log/api_requests_<log_id>_<suffix>.jsonl` (Fallback: `/tmp/dual_log/`).
Subfolder `src/logs/dual_log/` wird via `_write_entry` → `mkdir(parents=True, exist_ok=True)` automatisch angelegt.

**Envelope pro Zeile:**
```json
{"timestamp": "<iso>Z", "request_id": "<x-request-id or ''>", "model": "<model>", "payload": <full dict>}
```
`request_id` = `flow.request.headers.get("x-request-id", "")` — gleiche Quelle wie `_build_entry` → Original/Forwarded/Main-Log korrelierbar per `request_id`.

## Die zwei Snapshot-Punkte

### Snapshot 1 — `_original` (vor apply_modification_rules)

Schreibpunkt: unmittelbar VOR `apply_modification_rules(payload, ...)`.
`payload` ist der rohe CC-Payload aus `_parse_payload(body)`. Der Schema-Check davor (lines 80–90)
liest `payload`, mutiert ihn nicht. Weil sofort zu JSONL serialisiert wird, sind spätere In-Place-Mutationen
durch `apply_modification_rules` ohne Einfluss auf die bereits geschriebene Zeile.

`model`-Feld: `payload.get("model", "")` = das von CC angeforderte Modell vor jeglichem Override.

### Snapshot 2 — `_forwarded` (echtes Wire-Payload)

Schreibpunkt: unmittelbar VOR `flow.request.content = json.dumps(modified_payload).encode("utf-8")`.
`modified_payload` hat zu diesem Zeitpunkt die KOMPLETTE Pipeline durchlaufen — inklusive
`_strip_all_cache_control` (line 158) und `_set_cache_breakpoints` (line 159).

**Bewusster Unterschied zu `entry["raw_payload"]` (Main-Log, line 133):**
`entry` wird an line 133 gebaut — VOR den Cache-Ops (lines 158–159). `_forwarded` enthält also die
Proxy-eigenen `cache_control`-Breakpoints, `entry["raw_payload"]` nicht.
Das ist gewollt: `_forwarded` = exakt was Anthropic empfängt, byte-identisch zum Wire-Payload.

`model`-Feld: `modified_payload.get("model", "")` = ggf. überschriebener Model-Wert nach `_inject_model_override`.

## Was NICHT geändert wurde

- Bestehende Log-Writes: schema_warning (line 84), Main-Entry (line 152), sent_meta (line 173), latency_update (line 287) — byte-identisch.
- Proxy-Modifikationslogik: `apply_modification_rules`, `_strip_unused_tools`, `inject_mcp_tools`, `_strip_tool_descriptions`, `_strip_sys3`, `_strip_blocked_tool_references`, `_inject_context_management`, `_inject_model_override`, `_strip_all_cache_control`, `_set_cache_breakpoints` — alle unverändert.
- Monitor-Leseseite (`src/proxy_display/**`) — unberührt.
- `claude_proxy_start.sh`, `log_janitor.py`, `logging.py._build_entry` — unberührt.

## Orphan-Line-Verhalten

Wenn die Pipeline zwischen den beiden Writes mit einer Exception abbricht: `_original` hat eine Zeile,
`_forwarded` nicht. Bewusst informativ, nicht künstlich balanciert.

## De-Risking-Begründung

Erst nur Logging am realen Verkehr — bevor Monitor-Leseseite oder Janitor angefasst werden. Die neuen
Logs liefern den empirischen Baseline-Cut: welche Felder weichen Original vs. Forwarded tatsächlich ab,
wie groß sind die Files, reicht das Envelope-Format für spätere Differenzierung. Iteration danach datengetrieben.

## Nächste Iterationen (geplant, nicht gebaut)

1. **Message-Blöcke deltifizieren** — Tools + System-Blöcke bleiben pro Request voll (sie werden immer
   komplett gesendet), nur die Messages werden auf "neu seit letztem Request" reduziert. Analog zur
   bestehenden `diff_from_prev`-Logik in `logging.py`, aber direkt im `_forwarded`-Payload.

2. **Grün-für-injiziert** — zusätzlich zu Gelb-für-gestrippt im Monitor. Injektionen (wakeup-text,
   model-override, context-management, MCP-tools) im `_forwarded`-Log markieren, damit die Monitor-Anzeige
   Original↔Forwarded-Diff direkt coloriert.

3. **Monitor-Leseseite** — `src/proxy_display/` konsumiert `_original` als Anzeigebasis, überlagert
   `_forwarded` für Strip-Highlighting. Erfordert Schema-Kompatibilitätsprüfung für alte Single-Log-Sessions.

4. **Janitor 4 Kategorien** — `_LOG_REGISTRY` in `src/log_janitor.py`: 2 api_requests-Kategorien
   (opus, worker) → 4 (opus-original, opus-forwarded, worker-original, worker-forwarded). `count-30`-Logik
   auch in `claude_proxy_start.sh` anpassen. Retention-Strategie: `dual_log/`-Subfolder vs. Hauptverzeichnis TBD.
