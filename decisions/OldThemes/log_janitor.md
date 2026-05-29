# Log Janitor — Audit + Decisions (2026-05-28)

## Context

Audit-Session 2026-05-28. Three gaps found in Monitor_CC's own log files — two append-forever JSONL logs without cleanup, one growing plain-text log, and circular dead-code in the proxy startup script.

---

## GAP 1 — tool_errors.jsonl + hook_firing.jsonl (7-day retention)

### Finding

Both files are append-forever with no cleanup:

| File | Writer | `ts` format | Cleanup |
|---|---|---|---|
| `src/logs/hook_firing.jsonl` | `_fire_log.log_fire()` (in `src/hooks/`) | `"%Y-%m-%dT%H:%M:%SZ"` (UTC+Z, stable) | none |
| `src/logs/tool_errors.jsonl` | `warnings_persist.append_tool_errors()` (in `src/panes/`) | `err.get('_ts_raw', '') or err.get('timestamp', '')` — proxy-derived, variable, can be empty | none |

### Trigger Decision — Why Not Menubar Bundle

First proposal: extend Menubar's 24h tick in `app.py` (pattern: `_last_log_cleanup_ts`, 86400s guard). Rejected:

The Menubar runs as py2app bundle. `Path(__file__).parent.parent / 'logs'` from inside the bundle resolves to the PRUNED BUNDLE directory (`MonitorCC.app/Contents/Resources/lib/.../src/logs/`), NOT `main-repo/src/logs/`. Both JSONL writers resolve paths from their own `__file__` location in the main repo. Bundle tick → wrong path → janitor no-op on non-existent bundle logs. Same class of divergence as the historical `menubar.log`-path bug.

### Correct Trigger — run_main_loop() in src/core/monitor.py

- Runs from main repo (started via `workflow.py`, no bundle)
- Default mode — always active when Monitor_CC is running
- Existing `POLL_INTERVAL` tick provides natural throttle point
- Pattern: `_last_janitor_ts = 0.0` local var before `while True:`, 24h check inside the `if now - last_data_refresh >= POLL_INTERVAL:` block
- `Path(__file__).parent.parent / 'logs'` from `src/core/monitor.py` = `src/logs/` ✓ (matches writer paths)

### Module Placement — src/log_janitor.py

Alternatives rejected:
- `src/jsonl/` — CC session parsing package (`~/.claude/projects/**/*.jsonl`), wrong concern
- `src/utils.py` — display utilities (format_timestamp, _cell_width), wrong abstraction

`src/log_janitor.py` at `src/` root: standalone utility, stdlib-only, no cross-package deps. Import in `monitor.py`: `from ..log_janitor import cleanup_old_jsonl`.

### 7-day Retention Policy

Consistent with `menubar_log.py:RETENTION_SECS = 7 * 86400` (already established). No discussion needed.

### ts-Format Robustness

`hook_firing.jsonl`: always `"YYYY-MM-DDTHH:MM:SSZ"` → `.replace('Z', '+00:00')` → UTC-aware parse ✓  
`tool_errors.jsonl` empty ts: `if ts_raw:` guard → keep ✓  
`tool_errors.jsonl` naive ts (no TZ from proxy): `fromisoformat` returns naive datetime → comparison with UTC-aware cutoff raises `TypeError` → outer `except Exception` → keep (fail-safe) ✓

### Implementation

- `src/log_janitor.py:cleanup_old_jsonl(path: Path)` — 33 LOC, fail-silent (comments on `except` lines to satisfy `block_except_pass` hook)
- Trigger: `src/core/monitor.py:run_main_loop()`, 24h guard, `_logs = Path(__file__).parent.parent / 'logs'`
- Smoke: `dev/hook_smoke/test_log_janitor.py` (4 cases — old drop, recent keep, empty ts keep, naive ts keep)

---

## GAP 2 — src/gpu_pane/logs/gpu_pane.log (rotation)

### Finding

`src/gpu_pane/status.py` uses `logging.FileHandler` (plain append, no rotation). Format: Python asctime `YYYY-MM-DD HH:MM:SS,mmm WARNING <msg>`. Was 50MB in old bundle (gitignored directory).

### Options evaluated

| Option | Where | Mechanism | Decision |
|---|---|---|---|
| `RotatingFileHandler(maxBytes=5MB, backupCount=2)` | `status.py` | size-based, max ~15MB | rejected — no time-based expiry |
| `TimedRotatingFileHandler(when='d', backupCount=7)` | `status.py` | daily rotation, 7 days | **chosen** |
| External cleanup in `cleanup_old_jsonl` flow | `monitor.py` 24h tick | needs separate parser for non-JSON format | rejected — more complex, different format |

### Decision

`TimedRotatingFileHandler(when='d', interval=1, backupCount=7)` — rotates daily, keeps 7 days. Self-contained in `status.py`, no external trigger. 7-day retention consistent with rest of project.

---

## Dead Code — proxy_errors_*.log Removal

### Finding

`src/claude_proxy_start.sh`:
- Line 192 (before fix): `mitmdump ... 2>"$LOG_DIR/proxy_errors_$LOG_ID.log"` — per-session stderr file
- `_janitor_cleanup_jsonl_logs()`: deletion loop removes all `proxy_errors_*.log` on next startup
- Comment in code: "companion disabled, files are dead weight"
- Net effect: circular — each session creates one file, next session deletes it. Always exactly one live file with zero retention value.

### Decision

`2>/dev/null` for mitmdump stderr, deletion loop removed.

Alternatives considered:
- `proxy_errors.log` (shared, `>` overwrite) — keeps last session's errors for debugging; rejected because the "companion disabled, files are dead weight" comment makes intent clear: these files serve no purpose.
- `/dev/null` — no residual files, clean. If mitmdump crashes the exit signal is visible in the monitor process. Chosen.

Changes made:
1. `local` declaration: `deleted_errors=0` removed
2. Lines 168–173 (deletion loop + preceding blank line + comment): removed
3. `echo` line: `deleted_errors` fragment removed
4. Line 192: `2>"$LOG_DIR/proxy_errors_$LOG_ID.log"` → `2>/dev/null`

---

## Stage 3 — Unified Janitor + count_tokens-Fix (2026-05-29)

### count_tokens-Prädikat-Befund

`_is_messages_request()` (addon.py) nutzte `flow.request.path.startswith("/v1/messages")`. Aus 108 `api_error_payload_*.json`-Dateien:
- 105 × `request_url` = `.../v1/messages/count_tokens?beta=true` → count_tokens wurde als Messages-Request klassifiziert
- 3 × `request_url` = `.../v1/messages?beta=true` → echte Messages (400 durch base64-Fehler, korrekt erfasst)

CC sendet count_tokens immer mit Query-String `?beta=true`. Echte Messages ebenfalls. Prädikat-Fix: exakter Match auf den Messages-Endpoint:
```python
path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?")
```
Damit läuft `/v1/messages/count_tokens?...` KOMPLETT unverändert durch die Proxy-Pipeline — kein Inject, kein Log-Entry, keine 400er.

### api_errors.jsonl-Format

Rollende JSONL statt Einzeldateien. Felder: `ts` (nicht `timestamp`, damit `cleanup_old_jsonl` greift), `status_code`, `error_response`, `request_url`, `request_payload`. Writer: `_write_entry(self.log_file.parent / "api_errors.jsonl", error_data)`.

### LogSpec-Registry-Design

**Analyse sweep-fähig vs extern:**

| Policy | Warum sweep-fähig / nicht |
|---|---|
| tool_errors, hook_firing, api_errors | ts-basierter Record-Drop via `cleanup_old_jsonl` — trivial, Python, monitor-24h ✅ |
| api_requests opus/worker count-30 | count-basiert, Bash, vor Monitor-Start nötig ❌ |
| gpu_pane.log | `TimedRotatingFileHandler` im gpu_pane-Prozess selbst — kein externer Sweep möglich ❌ |
| ccwrap *.bin/*.ansi.log | `rotate_logs` ist Caller-getriggert (kein Alter-Sweep) ❌ |

**Entscheidung:** Registry inventarisiert ALLE Logs als `LogSpec`-Einträge. `sweep_eligible=True` für die drei ts-record-Logs. `sweep_eligible_specs()` gibt nur diese zurück. `monitor.py` iteriert über Registry statt Pfade hardzukodieren — neue sweep-fähige Logs werden durch Registreintrag automatisch eingeschlossen.

### Orphan-Cleanup — Verankerung

Alle drei Orphan-Typen in `_janitor_cleanup_jsonl_logs` (proxy-start-bash), idempotent:
- `api_error_payload_*.json` → `find ... -delete` (writer entfernt → no-op ab zweitem Start)
- `proxy_errors_*.log` → `find ... -delete` (writer auf `2>/dev/null` seit Stage 2 → no-op ab zweitem Start)
- `tool_use_errors.jsonl` → `rm -f` (kein Writer — permanent no-op nach erstem Lauf)

Vorherige `find ... -mtime +7 -delete` Zeile (post-mitmdump) entfernt — Cleanup vollständig in `_janitor_cleanup_jsonl_logs` konsolidiert.
