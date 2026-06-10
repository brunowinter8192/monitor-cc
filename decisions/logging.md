# Log Inventory — Monitor_CC

## Status Quo (IST)

### Log-Tabelle

| Name | Datei | Writer | Reader | Zweck | Format | Retention | Janitor-Trigger |
|---|---|---|---|---|---|---|---|
| hook_firing | `src/logs/hook_firing.jsonl` | `hooks/*:log_fire` | (Debug/Analyse) | Hook-Execution-Events (PreToolUse / PostToolUse Firings) | JSONL (`ts`-Feld, UTC+Z) | 7d-ts-records | monitor-24h |
| api_errors | `src/logs/api_errors.jsonl` | `proxy/addon.py:ProxyAddon.response` | (Debug/Analyse) | 4xx-API-Fehler aus mitmproxy: Status, Error-Body, Request-URL, Request-Payload | JSONL (`ts`-Feld) | 7d-ts-records | monitor-24h |
| api_requests_dual_original | `src/logs/dual_log/api_requests_<log_id>_original.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | (Analyse) | Roher CC-Payload VOR Modifikation (pre-apply_modification_rules) | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_forwarded | `src/logs/dual_log/api_requests_<log_id>_forwarded.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `parse_proxy_log_forwarded` / `_parse_forwarded_log` (Stage 2C) | Delta-Log des weitergeleiteten (post-Modifikation) Payloads; trägt `max_tokens` + `output_config` + `context_management` + `diagnostics`-Felder (body-field passthrough; Stage 1 addition) | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_stripped | `src/logs/dual_log/api_requests_<log_id>_stripped.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (yellow overlay) | Delta-Log: was der Proxy aus dem Original entfernt hat | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_injected | `src/logs/dual_log/api_requests_<log_id>_injected.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/pane.py` + `worker_proxy_pane.py` via `accumulate_dual_log` (green overlay) | Delta-Log: was der Proxy in den forwarded Payload injiziert hat | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_errors | `src/logs/dual_log/api_requests_<log_id>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `find_errors_log_path` + `_read_errors_log` (Stage 2D) | Derived tool-error log: `is_error=True` tool_result blocks extrahiert aus dem Original-Payload, dedup by `tool_use_id` per model_family; Format: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}` | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_dual_response | `src/logs/dual_log/api_requests_<log_id>_response.jsonl` | `proxy/addon.py:_resolve_dual_log_file` | `proxy_display/parser.py:find_response_log_path` + `read_response_log` → `panes/token_pane.py` via `request_id`-Join; renders rate-limit (5h/7d utilization + reset) in expanded token-pane call block | Response-HTTP-Header der Rate-Limit-Familie + request-id, joined by flow_id; gefiltert via `_filter_response_headers` (exact: `request-id`, `retry-after`, `anthropic-organization-id`; prefix: `anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`); geschrieben in `responseheaders()`-Hook für ALLE Status-Codes (inkl. 429 retry-after); Format: `{flow_id, timestamp, request_id, status_code, headers: {…}}` | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| api_requests_worker_dual_errors | `src/logs/dual_log/api_requests_worker_<hash>_<name>_<ts>_errors.jsonl` | `proxy/addon.py` via `logging.py:_build_errors_entries` | `panes/warnings_pane.py` via `scan_worker_errors_logs` (Stage 2D) | Worker-session derived tool-error log; same format as `_errors`; worker_name extracted from filename | JSONL | count-30 (suffix-aligned) | proxy-start-bash |
| gpu_pane | `src/gpu_pane/logs/gpu_pane.log` | `gpu_pane/status.py:TimedRotatingFileHandler` | (kein aktiver Reader) | GPU-Monitoring-Statusmeldungen | Python-Log (`YYYY-MM-DD HH:MM:SS,mmm <level> msg`) | 7d-timed-rotation | live-handler |
| ccwrap_session | `src/ccwrap/logs/<stem>.bin + <stem>.ansi.log` | `ccwrap/ansi_log.py:open_log_pair` | (Debug/Analyse) | Rohe ANSI-Terminal-Captures von CC-Sessions | Binary + ANSI-Tab-TSV | count-10-pairs | ccwrap-caller |
| polling_state | `src/logs/polling_state.jsonl` | `hooks/block_polling_loop.py:_record_and_count` | (kein Reader) | Polling-Frequenz-State für block_polling_loop hook (session×target Zähler, self-pruned auf 30 s Fenster) | JSONL (`ts`-Feld) | 1d-ts-records | monitor-24h |

### Zwei-Trigger-Architektur

**Trigger 1 — proxy-start-bash** (`src/claude_proxy_start.sh:_janitor_cleanup_jsonl_logs` + `_janitor_version_purge_jsonl_logs` + `_compute_proxy_hash`):
- Zuständig für `dual_log/` — per-class split: opus-originals keep-30 + worker-originals keep-30 getrennt; vorangestellt: version-aware purge (Phase 0)
- Phase 0 (version-purge, `_janitor_version_purge_jsonl_logs`): Content-Hash (`_compute_proxy_hash`) über `proxy_addon.py` + `proxy/**/*.py` + `proxy/**/*.json` (sort-stabil via `find … | sort`; schließt `*.pyc`, `*.md`, `.DS_Store` aus). Marker `dual_log/.proxy_version` (1 Zeile = letzter Hash). Hash-Änderung oder fehlender Marker → `find dual_log/ -maxdepth 1 -name "api_requests_*.jsonl" -mmin +60 -delete`; danach Marker schreiben. Fehlender Marker = First-Run = treated as change (bereinigt alte Logs beim ersten versions-aware Start). mtime < 60min = lebendige Session = überlebt den Purge.
- Phase 1a: `ls -t dual_log/api_requests_opus_*_original.jsonl | tail -n +31` → delete
- Phase 1b: `ls -t dual_log/api_requests_worker_*_original.jsonl | tail -n +31` → delete
- Phase 2: surviving `log_id`s = union from remaining `_original` files after rotation
- Phase 3: alle anderen `dual_log/api_requests_*.jsonl` ohne passende `log_id` gelöscht (suffix-stripping: original/forwarded/stripped/injected/errors/response — alle Suffixe einer log_id gemeinsam rotiert, suffix-aligned)
- Marker-Staleness: zeigt auf `dual_log/api_requests_<log_id>_forwarded.jsonl` (nicht mehr Haupt-Log) — mtime-Check prüft ob aktive Session; <60s → MARKER_IS_STALE=false
- Läuft bei jedem Proxy-Start — unabhängig davon ob Monitor aktiv ist
- Bash (kein Python): count-basierte Rotation via `ls -t | tail -n +31` ist trivial in Shell

**Trigger 2 — monitor-24h** (`src/core/monitor.py:run_main_loop`, 86400s-Guard):
- Zuständig für die sweep-fähigen JSONL-Logs (hook_firing, api_errors, polling_state)
- Python: `cleanup_old_jsonl(path)` aus `src/log_janitor.py` über `sweep_eligible_specs(logs_dir)`
- Path-Auflösung: `Path(__file__).parent.parent / 'logs'` aus `src/core/monitor.py` = `src/logs/` ✓

**Nicht sweep-fähig (Handler/Caller-basiert):**
- `gpu_pane.log` → `TimedRotatingFileHandler` lebt im gpu_pane-Prozess selbst
- `*.bin + *.ansi.log` → `ccwrap/ansi_log.py:rotate_logs` wird vom ccwrap-Caller getriggert

### LogSpec-Registry

`src/log_janitor.py` enthält `_LOG_REGISTRY` (Tuple aus 11 `LogSpec`-Einträgen, alle Logs inventarisiert). `sweep_eligible_specs(logs_dir)` gibt `(spec, path)`-Paare für die monitor-24h-Logs zurück. `monitor.py` iteriert darüber — neue sweep-fähige Logs werden durch Hinzufügen eines Eintrags in `_LOG_REGISTRY` automatisch eingeschlossen.

`polling_state.jsonl` ist primär self-pruning (block_polling_loop prunt Einträge > 30 s bei jedem Aufruf). Der monitor-24h Sweep via `cleanup_old_jsonl` ist ein Backup für den Fall, dass der Hook-Prune wiederholt fehlschlug (z. B. I/O-Fehler). Die effektive Retention im Normalbetrieb ist 30 Sekunden.

### Message-Span Diffing (Strip/Inject)

`messages_delta` spans in `_stripped` and `_injected` entries are built via operation-transcript composition. Per-block logic in `_build_stripped_injected_deltas` (`logging.py`):

- `_all_ops` (`{msg_idx: {blk_idx: [(offset, removed, injected)]}}`) returned from `apply_modification_rules` as 8th tuple element; stashed in `request()` as `flow.metadata["mc_all_ops"]`; read in `response()` and passed into `_build_stripped_injected_deltas(all_ops=...)`.
- Per block: `block_ops = msg_ops.get(bidx_int, [])` (empty default). `c0_text` extracted from orig content for all blocks via `_get_inner_text`. `spans = compose_block(c0_text, block_ops)` always — no `_diff_text` fallback for messages. Op-less (unmodified) blocks: `block_ops=[]` → `[("equal", c0_text)]` → `s_texts=[]`, `has_i=False` → nothing written. Output-unchanged vs pre-Stage-4 for unmodified blocks: verified.
- `_diff_text` not called for messages (Stage 4). `_diff_messages` produces block structure only (`{bidx, o_text, f_text}`, no `spans` field). `_diff_text` remains for system/tools (`_diff_system`, `_diff_tools`).
- Guard against mutation-without-op: `dev/proxy_dual_log/test_composition_invariant.py` — committed synthetic fixture (9 entries, all 8 passes + dedup_wakeup + money-shot), exit 1 on any invariant violation. No runtime fallback.
- Double-inject fixed: TN+BG chain produces 3 ops on msg[N] blk[0] (first_pass TN-strip+wakeup-inject, bg_exit BG-strip+wakeup-inject, dedup_wakeup removes 2nd wakeup). `compose_block` yields exactly 1 injected wakeup span — offline-verified on money-shot msg[100]: wakeup_count=1, has_i=True, badge fires. LIVE-VERIFY pending (proxy restart required).
- Inner-content level: `_get_inner_text` returns `block["text"]` for text blocks, `block["content"]` for tool_result.

`compose_block`, `apply_edit_to_spans`, and `_get_inner_text` live in `src/proxy/diff_engine.py`.

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
- ✅ **Badge false-positive fix** — four phantom `fn_map` sources eliminated; verified on real logs. **`fn_map` attribution rules:** (1) field overrides (`field.*` loc_keys — model, max_tokens, thinking, output_config, context_management) NOT written to `fn_map` at write-side in `_build_stripped_injected_deltas`; they appear only in `fields_delta`; (2) message, system, and tools-desc blocks whose only injected text is `"."` (empty-block placeholder — `strip_sr.py` `or '.'`, `_strip_sys3()` unconditional `"."`, `_apply_system_passes()` empty-rules `"."`) NOT written to `fn_map`; overlay dicts (`i_sys`/`i_tools`/`i_blks`) remain set; (3) `strip_sr.py` partial mode preserves original trailing-`\n` — no longer forwards a net-new `\n` when the original SR had none. Read-side `accumulate_dual_log` uses `set(fn_map.values())` (no `field.*` filter needed). Detail: `decisions/OldThemes/proxy_tool_stripping/17_badge_false_positives.md`
- ⏳ **2E remaining:** (c) full live-verify on new-format logs needs proxy restart

**Stage 3 — Write-side removal (DONE):**
- ✅ `api_requests_<id>.jsonl` write path removed: `_build_entry` / `_build_latency_update` / `_count_system_chars` / `_summarize_content_for_log` deleted from `proxy/logging.py`; main-log `_write_entry` calls + latency hook removed from `proxy/addon.py`
- ✅ `proxy/hash_meta.py` deleted (sent_meta writer + drift-report helpers — no callers)
- ✅ `proxy/schema_check.py` deleted (schema-warning writer — no callers after Block A)
- ✅ `tool_errors` + `api_requests_opus` + `api_requests_worker` LogSpec entries removed from `src/log_janitor.py:_LOG_REGISTRY`
- ✅ `warnings_persist.py` deleted; `warnings_scan.py` deleted
- ✅ 0:main strip overlay removed (`_refresh_strip_cache`, `ingest_proxy_strip_data`, `_strip_by_tool_id`, `_strip_prompt_ts_set`, `build_tool_id_strip_lookup`)
- ✅ 9 dead parser fns deleted (`_enrich_content_tails`, `_lazy_load_messages`, `_extract_raw_payload_fields`, `_parse_log_file`, `parse_proxy_log`, `scan_worker_logs`, `_subprocess_worker`, `_parse_log_file_isolated`, `parse_proxy_log_isolated`)
- ✅ Rotation re-anchored to `_original` files (per-class opus-30 + worker-30 split); marker staleness → `_forwarded.jsonl`; pre-existing `_errors` suffix bug fixed
- ✅ `find_worker_proxy_log` updated: dual-log forwarded discovery as primary (globs `dual_log/api_requests_worker_*_forwarded.jsonl`), legacy main-log as fallback
