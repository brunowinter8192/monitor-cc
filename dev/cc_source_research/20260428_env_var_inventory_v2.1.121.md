# Claude Code Env-Var Inventory — v2.1.121

**Bead:** Monitor_CC-t1i, Sub-Frage 1  
**Date:** 2026-04-28  
**Binary:** `@anthropic-ai/claude-code-darwin-arm64@2.1.121` (Mach-O arm64, 205 MB)

---

## 1. Source + Methodology

### Binary Version

```
npm view @anthropic-ai/claude-code version  →  2.1.121  (latest as of 2026-04-28)
```

Kein neueres Release seit dem ersten Research-Pass. Binary noch in `/tmp/package/claude`.

### Extraction

```bash
# Step 1 — alle CLAUDE_* Strings
grep -oa "CLAUDE_[A-Z][A-Z_]*" /tmp/package/claude | sort -u  →  291 Strings

# Step 2 — perf-adjacent Non-CLAUDE_ Strings
grep -oa "API_TIMEOUT_MS|ANTHROPIC_[A-Z][A-Z_]*|FALLBACK_FOR_[A-Z_]*|USE_API_[A-Z_]*" \
     /tmp/package/claude | sort -u  →  52 Strings
```

### Confirmed-Read Kriterium

| Tier | Definition |
|---|---|
| ✅ Confirmed | Erscheint in `thepono1/INSIGHTS.md` (v2.1.88 TS-Source-Extract) ODER in `alanisme/claude-code-decompiled` docs ODER via #33949 empirischer Reverse-Engineering |
| ⚠️ Post-leak | Im Binary, NICHT in v2.1.88-Source — wahrscheinlich nach dem Source-Map-Leak (Apr 2026) hinzugefügt. Read-Site nicht direkt verifiziert, aber Name-Pattern = eindeutig funktionaler Env-Var (kein Partial-String). |
| 🔤 Fragment | Pattern-Prefix im Binary (z.B. `CLAUDE_CODE_DISABLE_` ohne Suffix) — wird dynamisch zu vollständigen Var-Namen konkateniert. Kein eigenständiger Var-Name. |

---

## 2. Env-Vars — Latency / Stream / Retry

*Direkte Auswirkung auf TTFB, Stream-Stalls, Timeout-Verhalten, Retry-Logic.*

| Name | Confirmed | Default | Effect | doc_mentioned |
|---|---|---|---|---|
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | ✅ | `90000` (90 s) | Client-seitiger Idle-Timer auf SSE-Stream. Läuft ab → "API Error: Stream idle timeout". Reset auf jeden Chunk. Empirisch gemessen: alle Timeouts 90.0–91.7 s (CaptFaraday, #49500). | Nein |
| `CLAUDE_ENABLE_STREAM_WATCHDOG` | ✅ | off | 30 s Warning + 60 s Abort (via AbortController) + Non-Streaming Retry. Reset auf jeden SSE-Frame (auch `:ping`). **Seit v2.1.50 im Code, default disabled.** Kolkov #33949. | Nein |
| `CLAUDE_ENABLE_BYTE_WATCHDOG` | ⚠️ | off | Byte-Level-Variant des Stream-Watchdog (post-v2.1.88). Vermutlich trackt echte Content-Bytes statt SSE-Frames → fixt das "ping resets watchdog"-Problem von `ENABLE_STREAM_WATCHDOG`. Genaue Schwellwerte unbekannt. | Nein |
| `CLAUDE_SLOW_FIRST_BYTE_MS` | ⚠️ | unbekannt | TTFB-spezifischer Threshold. Überschreitung löst Logging/Telemetrie aus — **kein Abort**, rein diagnostisch. Direkt nützlich für Monitor_CC TTFB-Diagnose. | Nein |
| `API_TIMEOUT_MS` | ✅ | unbekannt | Top-Level HTTP-Request-Timeout über den gesamten API-Call. **Separate Variable** von `CLAUDE_STREAM_IDLE_TIMEOUT_MS` — kontrolliert verschiedene Timeouts. Default unbekannt. | Nein |
| `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` | ⚠️ | unbekannt | Stall-Timeout für async Hintergrund-Agents (Task mit `run_in_background: true`). Ergänzt `CLAUDE_STREAM_IDLE_TIMEOUT_MS` für den Agent-Kontext. | Nein |
| `CLAUDE_CODE_RETRY_WATCHDOG` | ⚠️ | unbekannt | Kontrolliert Retry-Watchdog-Verhalten. Genauer Mechanismus unbekannt — vermutlich Retry-Count-Cap oder Retry-Backoff-Override für Dead-Connection-Recovery. | Nein |
| `CLAUDE_CODE_MAX_RETRIES` | ✅ | unbekannt | Maximale Anzahl API-Request-Retries bevor Hard-Error. | Nein |
| `CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK` | ✅ | not set (fallback aktiv) | Deaktiviert den Non-Streaming Retry-Pfad, den `CLAUDE_ENABLE_STREAM_WATCHDOG` nach Abort nutzt. Sinnvoll wenn man Abort ohne Retry will. | Nein |
| `CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS` | ✅ | not set | Verhindert dass Fast-Mode-Cooldown durch Netzwerkfehler getriggert wird. Hält Fast-Mode aktiv trotz transienter Fehler. | Nein |
| `CLAUDE_CODE_STALL_TIMEOUT_MS_FOR_TESTING` | ✅ | not set | Stall-Timeout Override für Tests — **nicht für Produktion gedacht**, kein sinnvoller User-Wert. | Nein |
| `CLAUDE_CODE_SLOW_OPERATION_THRESHOLD_MS` | ✅ | unbekannt | Threshold für Slow-Operation-Telemetrie-Logging. Kein Abort, rein diagnostisch. | Nein |
| `CLAUDE_CODE_REMOTE_SEND_KEEPALIVES` | ✅ | unbekannt | Steuert ob der Client Keepalives an Remote-Sessions sendet. Relevant für Remote-/Bridge-Modus wo der Client dormant sein kann. | Nein |

---

## 3. Env-Vars — Model / Routing / Capacity

| Name | Confirmed | Default | Effect | doc_mentioned |
|---|---|---|---|---|
| `ANTHROPIC_MODEL` | ✅ | — | Model-Override (höchste Priorität nach CLI `--model`). | Ja |
| `CLAUDE_CODE_SUBAGENT_MODEL` | ✅ | — | Model für Subagents — von Main-Loop-Model trennbar. | Nein |
| `ANTHROPIC_SMALL_FAST_MODEL` | ✅ | `claude-haiku-4-5` | Small/Fast-Model für Compaction, Subagent-Tasks, Background-Work. Default Haiku. Fehlkonfiguration hier = bekannte Ursache für Stalls (#26224). | Ja |
| `FALLBACK_FOR_ALL_PRIMARY_MODELS` | ✅ | not set | Aktiviert Fallback für ALLE Primary-Models bei Overload — nicht nur für Fast-Mode-Opus. Ergänzt `--fallback-model` CLI-Flag. | Nein |
| `CLAUDE_CODE_DISABLE_FAST_MODE` | ✅ | not set | Deaktiviert Fast-Mode (Priority-Serving für Opus 4.6, 6× Preis). | Nein |
| `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK` | ✅ | not set | Überspringt Org-Eligibility-Check für Fast-Mode. | Nein |
| `CLAUDE_CODE_RATE_LIMIT_TIER` | ✅ | — | Override des Rate-Limit-Tiers. | Nein |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | ✅ | model-dependent | Max-Context-Token-Override. | Nein |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | ✅ | 8192 (escalates to 64k) | Max-Output-Token-Override. Default 8 k, eskaliert auf 64 k bei `max_output_tokens_recovery`. | Nein |
| `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` | ✅ | unbekannt | Max gleichzeitige Tool-Calls — Parallelität von Streaming-Tool-Execution. | Nein |
| `CLAUDE_CODE_EFFORT_LEVEL` | ✅ | `unset` / `auto` | Effort-Level-Override. `"unset"` oder `"auto"` deaktiviert Effort-Steuerung komplett. | Nein |
| `CLAUDE_EFFORT` | ✅ | — | Alternative Effort-Override-Var (kürzere Form). | Nein |
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` | ✅ | not set | Deaktiviert adaptives Thinking (dynamische Thinking-Budget-Anpassung). | Nein |
| `CLAUDE_CODE_DISABLE_THINKING` | ✅ | not set | Deaktiviert Extended-Thinking komplett. | Nein |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | ✅ | unbekannt | Prozentsatz des Context-Windows bei dem Auto-Compact triggert. | Nein |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | ✅ | unbekannt | Context-Window-Größe für Auto-Compact-Berechnung. | Nein |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | ✅ | `claude-haiku-4-5` | Custom Haiku-Model-Override. Fehlend/falsch → Stalls (bekannter Workaround in #26224). | Nein |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | ✅ | — | Custom Sonnet-Model-Override. | Nein |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | ✅ | — | Custom Opus-Model-Override. | Nein |
| `CLAUDE_CODE_ENABLE_FINE_GRAINED_TOOL_STREAMING` | ✅ | not set | Aktiviert feingranulares Tool-Streaming (Token-by-Token statt Block-Level). | Nein |

---

## 4. Env-Vars — Auth / API Connectivity

| Name | Confirmed | Default | Effect | doc_mentioned |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | API-Key für Direct-API-Zugang. | Ja |
| `CLAUDE_API_KEY` | ✅ | — | Alternative API-Key-Var (Legacy). | Ja |
| `ANTHROPIC_BASE_URL` | ✅ | `https://api.anthropic.com` | Base-URL-Override für API-Proxy oder Custom-Deployment. | Ja |
| `CLAUDE_CODE_API_BASE_URL` | ✅ | — | CC-spezifischer Base-URL-Override (überschreibt `ANTHROPIC_BASE_URL`). | Nein |
| `ANTHROPIC_LOG` | ✅ | — | Request-Logging-Level (`debug`, `info`, etc.). | Ja |
| `CLAUDE_CODE_EXTRA_BODY` | ✅ | — | Zusätzliche JSON-Felder im API-Request-Body. Wird direkt an `messages` API übergeben. | Nein |
| `ANTHROPIC_BETAS` | ✅ | — | Beta-Header (kommasepariert). | Ja |
| `ANTHROPIC_CUSTOM_HEADERS` | ✅ | — | Custom HTTP-Headers für alle API-Requests. | Nein |
| `CLAUDE_CODE_HTTP_PROXY` / `CLAUDE_CODE_HTTPS_PROXY` | ✅ | — | HTTP/HTTPS-Proxy für alle API-Connections. | Nein |
| `CLAUDE_CODE_PROXY_URL` | ✅ | — | Proxy-URL-Override (CC-spezifisch). | Nein |
| `ANTHROPIC_UNIX_SOCKET` | ✅ | — | Unix-Socket statt TCP für API-Verbindung. Relevant für Loopback-Proxy-Setups (wie Monitor_CC). | Nein |
| `CLAUDE_CODE_CERT_STORE` / `CLAUDE_CODE_CLIENT_CERT` / `CLAUDE_CODE_CLIENT_KEY` | ✅ | — | mTLS-Client-Zertifikate für Corporate-Proxy-Setups. | Nein |
| `CLAUDE_CODE_API_KEY_HELPER_TTL_MS` | ✅ | unbekannt | TTL für cached API-Key-Helper-Results. | Nein |

---

## 5. Env-Vars — Tool Execution / Session

| Name | Confirmed | Default | Effect | doc_mentioned |
|---|---|---|---|---|
| `CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS` | ✅ | unbekannt | Max-Token-Cap für File-Read-Tool-Output. Überschreitung → Truncation. | Nein |
| `CLAUDE_CODE_GLOB_TIMEOUT_SECONDS` | ✅ | unbekannt | Timeout für Glob-Operations. | Nein |
| `CLAUDE_CODE_PWSH_PARSE_TIMEOUT_MS` | ✅ | unbekannt | PowerShell-Parse-Timeout. | Nein |
| `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` | ✅ | unbekannt | Timeout für Session-End-Hooks. | Nein |
| `CLAUDE_CODE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | ✅ | not set | Hält das Working-Directory über Bash-Tool-Calls hinweg konsistent. | Nein |
| `USE_API_CONTEXT_MANAGEMENT` | ✅ | not set | Verwendet API-seitige Context-Management-Features. | Nein |
| `CLAUDE_CODE_ENABLE_TASKS` | ✅ | not set | Aktiviert Task-System. | Nein |
| `CLAUDE_CODE_IDLE_THRESHOLD_MINUTES` | ✅ | unbekannt | Idle-Schwellwert (Minuten) für Session-Idle-Detection. | Nein |
| `CLAUDE_CODE_IDLE_TOKEN_THRESHOLD` | ✅ | unbekannt | Token-Anzahl-Schwellwert für Idle-Detection (ergänzt `IDLE_THRESHOLD_MINUTES`). | Nein |

---

## 6. Env-Vars — Telemetry / Debug / Dev

| Name | Confirmed | Default | Effect | doc_mentioned |
|---|---|---|---|---|
| `CLAUDE_CODE_ENABLE_TELEMETRY` | ✅ | on | Telemetrie an/aus. Inkl. `tengu_streaming_stall` Events die Anthropic automatisch empfängt. | Nein |
| `CLAUDE_DEBUG` | ✅ | off | Debug-Modus — verbose Logging. | Nein |
| `CLAUDE_CODE_DEBUG_LOG_LEVEL` | ✅ | — | Debug-Log-Level-Override. | Nein |
| `CLAUDE_CODE_DEBUG_LOGS_DIR` | ✅ | — | Verzeichnis für Debug-Logs. | Nein |
| `CLAUDE_CODE_FRAME_TIMING_LOG` | ✅ | not set | Frame-Timing-Logging für Performance-Profiling. | Nein |
| `CLAUDE_CODE_COMMIT_LOG` | ✅ | not set | Aktiviert Commit-Log. | Nein |
| `CLAUDE_CODE_PROFILE_QUERY` | ✅ | not set | Profiling für Query-Pfad. | Nein |
| `CLAUDE_CODE_PROFILE_STARTUP` | ✅ | not set | Profiling für Startup. | Nein |
| `CLAUDE_CODE_PERFETTO_TRACE` | ✅ | — | Perfetto-Trace-Datei-Pfad. | Nein |
| `CLAUDE_CODE_SLOW_OPERATION_THRESHOLD_MS` | ✅ | unbekannt | Slow-Op Telemetrie-Threshold. | Nein |
| `CLAUBBIT` | ✅ | — | Feature-Flag-Override (GrowthBook-alternative für lokale Tests). | Nein |

---

## 7. Dead-Code / Fragment-Strings

Strings die im Binary als Prefix-Templates oder unvollständige Muster erscheinen — **keine eigenständigen Env-Vars**:

| String | Typ | Verwendung |
|---|---|---|
| `CLAUDE_CODE_` | Prefix-Fragment | Dynamisch zu vollständigem Var-Namen konkateniert |
| `CLAUDE_CODE_DISABLE_` | Prefix-Fragment | Template für `DISABLE_*` Vars |
| `CLAUDE_HAIKU_` | Prefix-Fragment | z.B. `CLAUDE_HAIKU_` + Modell-Suffix für Haiku-spezifische Overrides |
| `CLAUDE_OPUS_` | Prefix-Fragment | Analog für Opus |
| `CLAUDE_SONNET_` | Prefix-Fragment | Analog für Sonnet |
| `CLAUDE_PLUGIN_OPTION_` | Prefix-Fragment | `CLAUDE_PLUGIN_OPTION_` + Plugin-Name für Plugin-Optionen |
| `CLAUDE_BASE` | Unklar | Möglicherweise partieller Match von `CLAUDE_BASE_URL` o.ä. — kein eigenständiger Use-Case identifiziert |
| `CLAUBBIT` | Grenzfall | Im Binary, im INSIGHTS.md, aber kein klares Produktions-Use-Case |

---

## 8. Latency-Subset — Highlight + Recommendations

*Diese Vars haben direkten Einfluss auf TTFB / Stream-Stalls / Retry. Konkrete Empfehlungen.*

### Empfohlenes `~/.claude/settings.json` `env`-Block

```json
"env": {
  "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "300000",
  "CLAUDE_ENABLE_STREAM_WATCHDOG": "1",
  "CLAUDE_ENABLE_BYTE_WATCHDOG": "1",
  "CLAUDE_SLOW_FIRST_BYTE_MS": "8000"
}
```

### Rationale pro Var

| Var | Empfehlung | Begründung |
|---|---|---|
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | `300000` (5 min) | Default 90 s ist zu aggressiv für Opus 4.7 + Extended-Thinking + große Writes. 5 min → kein spuriouser Abort, aber Sessions die wirklich tot sind sterben noch binnen Session-Length. **Nicht** auf 1.800.000 setzen (CaptFaraday's Fix) — bei echtem Stall dauert dann die Fehlermeldung 30 min. |
| `CLAUDE_ENABLE_STREAM_WATCHDOG` | `1` | Aktiviert 30 s Warning + 60 s Abort + Retry. Fängt echte Dead-Connections. Nachteil: Reset auf `:ping` — Server-Keepalives können Watchdog dummy-resetten. Trotzdem besser als off. |
| `CLAUDE_ENABLE_BYTE_WATCHDOG` | `1` | Neuere Variant (post-v2.1.88), vermutlich byte-level statt frame-level → fixt den Ping-Reset-Flaw. Beide enablen bis klar ist welcher besser ist. |
| `CLAUDE_SLOW_FIRST_BYTE_MS` | `8000` | Loggt alle TTFB-Events > 8 s. Rein diagnostisch, kein Abort-Effekt. Wertvoll für Monitor_CC TTFB-Diagnose — erscheint dann in den Logs/Telemetrie. |
| `API_TIMEOUT_MS` | as-is (nicht setzen) | Unbekannter Default — besser nicht ändern ohne zu wissen was man überschreibt. Falls Stalls weiter auftreten: Wert aus Binary-Context ermitteln (Open Question). |
| `CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK` | not set (lassen) | Fallback ist nützlich — wenn Watchdog einen Stall erkennt und abbricht, soll der Non-Streaming Retry eine Chance haben. |
| `CLAUDE_CODE_RETRY_WATCHDOG` | as-is | Mechanismus unbekannt — nicht blind setzen. |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `claude-haiku-4-5` | Nur relevant wenn `ANTHROPIC_BASE_URL` auf Custom-Provider zeigt. Fehlend dort → bekannte Stall-Ursache (#26224). |

### Was Stalls NICHT behebt

- Keiner dieser Vars fixt server-seitige Stalls — sie verbessern nur wie der Client damit umgeht (früher abort, schnellere Recovery, bessere Diagnose).
- Der echte Fix wäre Anthropic-seitig: Watchdog default-enablen (Flip einer Boolean in ihrer Codebase, #33949 Prompt 1).
- `--fallback-model sonnet` CLI-Flag ist ein Runtime-Hedge für interaktive Nutzung wenn Opus der congested Pfad ist.

---

## 9. Open Questions

| Frage | Relevanz | Nächster Schritt |
|---|---|---|
| Was ist der Default-Wert von `API_TIMEOUT_MS`? | Hoch — könnte erklären warum manche User 5-min-Stalls ohne Stream-Idle-Error haben | Binary-Context-Analyse: Bytes um den String `API_TIMEOUT_MS` im Binary lesen, nach numerischen Werten suchen |
| Genauer Mechanismus von `CLAUDE_ENABLE_BYTE_WATCHDOG` — welcher Schwellwert, was triggert als "byte activity"? | Mittel — bestimmt ob er den Ping-Reset-Flaw tatsächlich fixt | Wartenn auf v2.1.88+ Source-Map-Leak oder weitere Binary-Analyse (Kontext-Bytes um String) |
| Was macht `CLAUDE_CODE_RETRY_WATCHDOG` genau? | Mittel — könnte ein weiteres Retry-Tuning-Lever sein | Binary-Context-Analyse |
| Default von `CLAUDE_SLOW_FIRST_BYTE_MS` — welcher Wert ist already "slow" laut Anthropic? | Mittel — setzt Baseline für TTFB-Diagnose | Binary-Context-Analyse oder Warten auf Source-Leak |
| ~~`CLAUDE_MOCK_HEADERLESS_429`~~ — war in INSIGHTS.md (v2.1.88), aber **nicht im v2.1.121 Binary**. Wurde zwischen v2.1.88 und v2.1.121 entfernt. | Geschlossen | Binary-Check ausgeführt: kein Match |
| Welche Vars wurden zwischen v2.1.88 und v2.1.121 hinzugefügt vs. entfernt? | Mittel — vollständiges Post-Leak Delta | `npm_version_diff_vars` Wishlist-Tool würde das lösen; manuell: v2.1.88 Binary downloaden + diff |
