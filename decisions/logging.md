# Log Inventory — Monitor_CC

## Status Quo (IST)

### Log-Tabelle

| Name | Datei | Writer | Reader | Zweck | Format | Retention | Janitor-Trigger |
|---|---|---|---|---|---|---|---|
| tool_errors | `src/logs/tool_errors.jsonl` | `panes/warnings_persist.py:append_tool_errors` | `panes/warnings_pane.py` (in-memory reload) | Tool-use-Fehler aus CC Hooks, Anzeige Warnings-Pane | JSONL (`ts`-Feld) | 7d-ts-records | monitor-24h |
| hook_firing | `src/logs/hook_firing.jsonl` | `hooks/*:log_fire` | (Debug/Analyse) | Hook-Execution-Events (PreToolUse / PostToolUse Firings) | JSONL (`ts`-Feld, UTC+Z) | 7d-ts-records | monitor-24h |
| api_errors | `src/logs/api_errors.jsonl` | `proxy/addon.py:ProxyAddon.response` | (Debug/Analyse) | 4xx-API-Fehler aus mitmproxy: Status, Error-Body, Request-URL, Request-Payload | JSONL (`ts`-Feld) | 7d-ts-records | monitor-24h |
| api_requests_opus | `src/logs/api_requests_opus_<project>_<ts>.jsonl` | `proxy/addon.py:_write_entry` | `proxy_display/parser.py`, `metadata/`, `panes/warnings_pane.py` | Vollständiger Proxy-Log: modifizierter Request + Response-Metadaten für Opus-Sessions | JSONL (multi-type entries) | count-30 | proxy-start-bash |
| api_requests_worker | `src/logs/api_requests_worker_<name>_<ts>.jsonl` | `proxy/addon.py:_write_entry` | `proxy_display/parser.py` (worker_proxy_pane) | Vollständiger Proxy-Log für Worker-Sessions | JSONL (multi-type entries) | count-30 | proxy-start-bash |
| gpu_pane | `src/gpu_pane/logs/gpu_pane.log` | `gpu_pane/status.py:TimedRotatingFileHandler` | (kein aktiver Reader) | GPU-Monitoring-Statusmeldungen | Python-Log (`YYYY-MM-DD HH:MM:SS,mmm <level> msg`) | 7d-timed-rotation | live-handler |
| ccwrap_session | `src/ccwrap/logs/<stem>.bin + <stem>.ansi.log` | `ccwrap/ansi_log.py:open_log_pair` | (Debug/Analyse) | Rohe ANSI-Terminal-Captures von CC-Sessions | Binary + ANSI-Tab-TSV | count-10-pairs | ccwrap-caller |
| polling_state | `src/logs/polling_state.jsonl` | `hooks/block_polling_loop.py:_record_and_count` | (kein Reader) | Polling-Frequenz-State für block_polling_loop hook (session×target Zähler, self-pruned auf 30 s Fenster) | JSONL (`ts`-Feld) | 1d-ts-records | monitor-24h |

### Zwei-Trigger-Architektur

**Trigger 1 — proxy-start-bash** (`src/claude_proxy_start.sh:_janitor_cleanup_jsonl_logs`):
- Zuständig für `api_requests_opus_*` + `api_requests_worker_*` (count-30)
- Läuft bei jedem Proxy-Start — unabhängig davon ob Monitor aktiv ist
- Bash (kein Python): count-basierte Rotation via `ls -t | tail -n +31` ist trivial in Shell

**Trigger 2 — monitor-24h** (`src/core/monitor.py:run_main_loop`, 86400s-Guard):
- Zuständig für die drei sweep-fähigen JSONL-Logs (tool_errors, hook_firing, api_errors)
- Python: `cleanup_old_jsonl(path)` aus `src/log_janitor.py` über `sweep_eligible_specs(logs_dir)`
- Path-Auflösung: `Path(__file__).parent.parent / 'logs'` aus `src/core/monitor.py` = `src/logs/` ✓

**Nicht sweep-fähig (Handler/Caller-basiert):**
- `gpu_pane.log` → `TimedRotatingFileHandler` lebt im gpu_pane-Prozess selbst
- `*.bin + *.ansi.log` → `ccwrap/ansi_log.py:rotate_logs` wird vom ccwrap-Caller getriggert

### LogSpec-Registry

`src/log_janitor.py` enthält `_LOG_REGISTRY` (Tuple aus 8 `LogSpec`-Einträgen, alle Logs inventarisiert). `sweep_eligible_specs(logs_dir)` gibt `(spec, path)`-Paare für die vier monitor-24h-Logs zurück. `monitor.py` iteriert darüber — neue sweep-fähige Logs werden durch Hinzufügen eines Eintrags in `_LOG_REGISTRY` automatisch eingeschlossen.

`polling_state.jsonl` ist primär self-pruning (block_polling_loop prunt Einträge > 30 s bei jedem Aufruf). Der monitor-24h Sweep via `cleanup_old_jsonl` ist ein Backup für den Fall, dass der Hook-Prune wiederholt fehlschlug (z. B. I/O-Fehler). Die effektive Retention im Normalbetrieb ist 30 Sekunden.

## Evidenz

- 108 `api_error_payload_*.json`-Dateien in `src/logs/`: 105/108 mit `request_url` = `https://api.anthropic.com/v1/messages/count_tokens?beta=true` — belegen, dass `_is_messages_request` via `path.startswith("/v1/messages")` count_tokens miterfasst und `_inject_model_override` `max_tokens` injiziert hat → API 400 `max_tokens: Extra inputs are not permitted`.
- `log_janitor.md` (in diesem Repo): Trigger-Entscheidung (Menubar-Bundle-Problem), ts-Format-Robustheit, Modul-Platzierung — Basis für die Zwei-Trigger-Architektur.

## Recommendation (SOLL)

Keep — Inventar und Registry vollständig und korrekt. `polling_state.jsonl` korrekt eingetragen (2026-05-29).
