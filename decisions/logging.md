# Log Inventory — Monitor_CC

## Status Quo (IST)

### Log-Tabelle

| Name | Datei | Writer | Reader | Zweck | Format | Retention | Janitor-Trigger |
|---|---|---|---|---|---|---|---|
| tool_errors | `src/logs/tool_errors.jsonl` | `panes/warnings_persist.py:append_tool_errors` (now stub — no longer written post Stage 2D) | (no active reader — orphaned log, Stage 3 cleanup pending) | Tool-use-Fehler aus CC Hooks, Anzeige Warnings-Pane — superseded by `_errors` dual-log | JSONL (`ts`-Feld) | 7d-ts-records | monitor-24h |
| hook_firing | `src/logs/hook_firing.jsonl` | `hooks/*:log_fire` | (Debug/Analyse) | Hook-Execution-Events (PreToolUse / PostToolUse Firings) | JSONL (`ts`-Feld, UTC+Z) | 7d-ts-records | monitor-24h |
| api_errors | `src/logs/api_errors.jsonl` | `proxy/addon.py:ProxyAddon.response` | (Debug/Analyse) | 4xx-API-Fehler aus mitmproxy: Status, Error-Body, Request-URL, Request-Payload | JSONL (`ts`-Feld) | 7d-ts-records | monitor-24h |
| api_requests_opus | `src/logs/api_requests_opus_<project>_<ts>.jsonl` | `proxy/addon.py:_write_entry` | **read-side migrated (Stage 2) — no active pane reader**; write still active (Stage 3 removes write path) | Vollständiger Proxy-Log: modifizierter Request + Response-Metadaten für Opus-Sessions | JSONL (multi-type entries) | count-30 | proxy-start-bash |
| api_requests_worker | `src/logs/api_requests_worker_<name>_<ts>.jsonl` | `proxy/addon.py:_write_entry` | **read-side migrated (Stage 2) — no active pane reader**; write still active (Stage 3 removes write path) | Vollständiger Proxy-Log für Worker-Sessions | JSONL (multi-type entries) | count-30 | proxy-start-bash |
| api_requests_dual_original | `src/logs/dual_log/api_requests_<log_id>_original.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | (Analyse) | Roher CC-Payload VOR Modifikation (pre-apply_modification_rules) | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| api_requests_dual_forwarded | `src/logs/dual_log/api_requests_<log_id>_forwarded.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `parse_proxy_log_forwarded` / `_parse_forwarded_log` (Stage 2C) | Delta-Log des weitergeleiteten (post-Modifikation) Payloads; trägt `max_tokens` + `output_config` + `max_tokens`-Felder (Stage 1 addition, required for proxy pane header) | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| api_requests_dual_stripped | `src/logs/dual_log/api_requests_<log_id>_stripped.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (yellow overlay) | Delta-Log: was der Proxy aus dem Original entfernt hat | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| api_requests_dual_injected | `src/logs/dual_log/api_requests_<log_id>_injected.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (green overlay) | Delta-Log: was der Proxy in den forwarded Payload injiziert hat | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| api_requests_dual_errors | `src/logs/dual_log/api_requests_<log_id>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `find_errors_log_path` + `_read_errors_log` (Stage 2D) | Derived tool-error log: `is_error=True` tool_result blocks extrahiert aus dem Original-Payload, dedup by `tool_use_id` per model_family; Format: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}` | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| api_requests_worker_dual_errors | `src/logs/dual_log/api_requests_worker_<hash>_<name>_<ts>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `scan_worker_errors_logs` (Stage 2D) | Worker-session derived tool-error log; same format as `_errors`; worker_name extracted from filename | JSONL | count-30 (quartet-aligned) | proxy-start-bash |
| gpu_pane | `src/gpu_pane/logs/gpu_pane.log` | `gpu_pane/status.py:TimedRotatingFileHandler` | (kein aktiver Reader) | GPU-Monitoring-Statusmeldungen | Python-Log (`YYYY-MM-DD HH:MM:SS,mmm <level> msg`) | 7d-timed-rotation | live-handler |
| ccwrap_session | `src/ccwrap/logs/<stem>.bin + <stem>.ansi.log` | `ccwrap/ansi_log.py:open_log_pair` | (Debug/Analyse) | Rohe ANSI-Terminal-Captures von CC-Sessions | Binary + ANSI-Tab-TSV | count-10-pairs | ccwrap-caller |
| polling_state | `src/logs/polling_state.jsonl` | `hooks/block_polling_loop.py:_record_and_count` | (kein Reader) | Polling-Frequenz-State für block_polling_loop hook (session×target Zähler, self-pruned auf 30 s Fenster) | JSONL (`ts`-Feld) | 1d-ts-records | monitor-24h |

### Zwei-Trigger-Architektur

**Trigger 1 — proxy-start-bash** (`src/claude_proxy_start.sh:_janitor_cleanup_jsonl_logs`):
- Zuständig für `api_requests_opus_*` + `api_requests_worker_*` (count-30) + `dual_log/` (quartet-aligned)
- Dual-Log-Rotation: nach der Haupt-Log-Rotation werden die überlebenden `log_id`s gesammelt; alle `dual_log/`-Files ohne passende `log_id` werden gelöscht. Verhindert Mtime-Divergenz-Orphans (die vier Suffixe werden zu unterschiedlichen Hook-Zeitpunkten geschrieben)
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

`src/log_janitor.py` enthält `_LOG_REGISTRY` (Tuple aus 12 `LogSpec`-Einträgen, alle Logs inventarisiert). `sweep_eligible_specs(logs_dir)` gibt `(spec, path)`-Paare für die vier monitor-24h-Logs zurück. `monitor.py` iteriert darüber — neue sweep-fähige Logs werden durch Hinzufügen eines Eintrags in `_LOG_REGISTRY` automatisch eingeschlossen.

`polling_state.jsonl` ist primär self-pruning (block_polling_loop prunt Einträge > 30 s bei jedem Aufruf). Der monitor-24h Sweep via `cleanup_old_jsonl` ist ein Backup für den Fall, dass der Hook-Prune wiederholt fehlschlug (z. B. I/O-Fehler). Die effektive Retention im Normalbetrieb ist 30 Sekunden.

## Evidenz

- 108 `api_error_payload_*.json`-Dateien in `src/logs/`: 105/108 mit `request_url` = `https://api.anthropic.com/v1/messages/count_tokens?beta=true` — belegen, dass `_is_messages_request` via `path.startswith("/v1/messages")` count_tokens miterfasst und `_inject_model_override` `max_tokens` injiziert hat → API 400 `max_tokens: Extra inputs are not permitted`.
- `log_janitor.md` (in diesem Repo): Trigger-Entscheidung (Menubar-Bundle-Problem), ts-Format-Robustheit, Modul-Platzierung — Basis für die Zwei-Trigger-Architektur.

**Main-log elimination feasibility probe (initial):**
- Script: `dev/proxy_dual_log/main_log_elimination_probe.py`
- Report: `dev/proxy_dual_log/main_log_elimination_probe_reports/20260604.md`
- Dataset: session `opus_monitor_cc_1780602018` at probe time (47 entries captured), positional match

| Check | Result |
|---|---|
| Content lossless (system/tools/messages) | ✅ 47/47 after cache_control-normalize (partial session — see full-session below) |
| Tool-error extraction vs tool_errors.jsonl | ✅ exact match (1 unique tool_use_id both sides) |
| BP:N counter derivable from quartet | ❌ pre-ops count not reconstructable — must be dropped |
| Missing top-level fields for proxy pane | `max_tokens` + `output_config` MUST-ADD to `_forwarded` |

**Full-session content-match verification (Stage 2B, readside2 worker):**
- Script: inline probe in readside2 verification session (reuses `_reconstruct_forwarded` + `_normalize_elem` logic from probe)
- Dataset: same session `opus_monitor_cc_1780602018`, all 118 entries at verification time (log grew as session is live)

| Check | Result |
|---|---|
| Content lossless system | ✅ 118/118 after cache_control-normalize |
| Content lossless tools | ✅ 118/118 |
| Content lossless messages | ✅ 118/118 |
| Malformed/truncated forwarded lines | 0 — no JSONDecodeError, no partial writes |
| 113-vs-115 discrepancy (2B probe vs ground truth) | Log is live; at 2B probe time parser consumed to EOF (new_pos==file_size verified); ground truth of 115 measured later; now 118. No parser bug. |

## Recommendation (SOLL)

**Change: eliminate the main log (`api_requests_<id>.jsonl`), derive the monitor read-side from the dual-log quartet.**

Feasibility proven by full-session probe (118/118 content lossless). Read-side migration complete (Stage 2 DONE). Remaining: Stage 3 — write-side removal.

**Stage 2 — Read-side migration (DONE except 2E remaining):**
- ✅ **2A:** `BP:N` counter + latency badge removed from proxy pane header (`render_turn.py`, `render_entry.py`, `format.py`)
- ✅ **2B:** `parser.py` forwarded-reconstruction core — `_parse_forwarded_log` (deque-bounded, `PROXY_MESSAGES_KEEP_LAST=10`), `_lazy_load_messages_forwarded`, `_summarize_fwd_message`/`_dict_to_list_fwd`/`_apply_delta_to_list`/`_extract_forwarded_fields` helpers; `find_errors_log_path`; `parse_proxy_log_forwarded`
- ✅ **2C:** `pane.py` + `worker_proxy_pane.py` wired to `parse_proxy_log_forwarded` / `_parse_forwarded_log`; state `_proxy_fwd_pos`/`_proxy_acc_fwd` replace `_proxy_pending_by_rid`; lazy-load uses `_lazy_load_messages_forwarded`
- ✅ **2D:** `warnings_pane` reads `_errors` dual-log (main session via `find_errors_log_path` + `_read_errors_log`; workers via `scan_worker_errors_logs`); `warnings_scan`/`warnings_persist` stubbed; `warnings_parse` gutted
- ✅ **2E.1:** `diff_from_prev` restored in `_parse_forwarded_log` via `_compute_diff(prev_summaries, curr_summaries)` (20/20 offline match vs main-log); `_is_standalone_entry` rewritten to content discriminator (`haiku OR sys_chars==0 AND tools_chars==0`), dropping `cache_breakpoints` guards — detail in `decisions/OldThemes/proxy_tool_stripping/15_main_log_elimination.md` § Stage 2E
- ✅ **2E.2:** request numbering + sidecar gate fixed — `diff_from_prev.messages_added > 0` trigger replaces dead `bp_len` / `entry_idx==0`; `opus_req_num` threads continuously (api_calls reseeding removed); `_is_standalone_entry` gate replaces haiku-only check; haiku→`'H'`, non-haiku sidecar→`'S'`; retry (`messages_added==0`) → `#N.M`; detail in `decisions/OldThemes/proxy_tool_stripping/15_main_log_elimination.md` § "Remaining after 2E.1 (a)"
- ✅ **2E.3:** SR/TN header badges (#4) — count badge re-sourced via `flow_id` join on `_stripped`/`_injected` `fn_map`; `{n}strip` (YELLOW) / `{n}inj` (GREEN) on REQ header; `_aggregate_entry_tags` removed. Detail: `decisions/OldThemes/proxy_tool_stripping/15_main_log_elimination.md` § "(b)"
- ⏳ **2E remaining:** (c) full live-verify on new-format logs needs proxy restart

**Stage 3 — Write-side removal (pending):**
- Remove `api_requests_<id>.jsonl` write path: `_write_entry` / `_build_entry` / `sent_meta` / `latency_update` / `schema_warning` from `proxy/addon.py` + `proxy/logging.py`
- Remove main-log `LogSpec` entry from `src/log_janitor.py:_LOG_REGISTRY` (count-30 janitor)
- Remove orphaned `tool_errors.jsonl` LogSpec (`src/log_janitor.py`) — writer stub, no reader
- Remove `append_tool_errors` stub from `warnings_persist.py` + its `LogSpec`
- Quartet count-30 janitor entry stays
