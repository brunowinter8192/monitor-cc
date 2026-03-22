# Pipe Section: Core Loop

## Status Quo

- `monitor.py`: `run_streaming_loop()` pollt alle 0.5s, ruft `process_hook_log()` + `monitor_sessions()` auf
- `monitor.py`: `run_rules_loop()` pollt alle 0.5s, ruft `process_hook_log()` auf und rendert `format_rules_block(active_rules)` bei Änderungen
- Hook routing in `process_hook_log()`: 3 Events → 3 State Dicts
  - `UserPromptSubmit` → `pending_user_prompt_hook`
  - `PreToolUse` → `pending_pretooluse_hooks`
  - `InstructionsLoaded` → `active_rules`
- Agent tracking: `agent_to_task`, `agent_to_type` maps, `buffered_subagent_calls` für Orphans (Calls ohne bekannten Agent)
- Usage accumulation: `accumulate_usage()` aggregiert Token-Totals pro Turn

`run_rules_loop()` Ablauf:
1. `process_hook_log()` → aktualisiert `active_rules`
2. `format_rules_block(active_rules)` → rendert ACTIVE RULES Block
3. Bei Änderung: Screen-Clear + Print
4. `time.sleep(POLL_INTERVAL)`

## IST — Stellschrauben

### Globale Mutable State — alle 18 Variablen (Kategorie: Architektur / Kopplung)

Alle Module-Level Variablen in `src/monitor.py` mit Zugriffs-Mapping:

| Variable | Typ | Definiert | Gelesen | Geschrieben | Beschreibung |
|----------|-----|-----------|---------|-------------|--------------|
| `file_positions` | `Dict[Path, int]` | monitor.py:60 | monitor.py | monitor.py | Byte-Offsets pro JSONL-Datei |
| `tool_use_caches` | `Dict[Path, dict]` | monitor.py:61 | monitor.py | monitor.py | tool_use_cache pro Session-Datei |
| `call_counter` | `int` | monitor.py:62 | monitor.py | monitor.py | Globaler Call-Zähler für Display |
| `agent_to_task` | `Dict[str, str]` | monitor.py:63 | monitor.py, ui_mode.py (via Argument) | monitor.py | agent_id → task tool_use_id |
| `agent_to_type` | `Dict[str, str]` | monitor.py:64 | monitor.py, ui_mode.py (via Argument) | monitor.py | agent_id → subagent_type |
| `buffered_subagent_calls` | `Dict[str, List[dict]]` | monitor.py:65 | monitor.py | monitor.py | Calls ohne bekannten Agent, kein TTL |
| `task_requests_seen` | `Set[str]` | monitor.py:66 | monitor.py | monitor.py | Gesehene Task-Request IDs |
| `active_project_filter` | `Optional[str]` | monitor.py:67 | monitor.py | monitor.py | Aktiver Projekt-Filter |
| `active_mode` | `str` | monitor.py:68 | monitor.py | monitor.py | Aktueller Mode (all/main/subagent/rules) |
| `ui_mode_active` | `bool` | monitor.py:69 | monitor.py | monitor.py | Flag: UI-Mode aktiv |
| `subagent_metadata` | `Dict[str, dict]` | monitor.py:70 | monitor.py, ui_mode.py (via Argument) | monitor.py | Subagent-Metadaten für UI |
| `tool_calls_by_agent` | `Dict[str, List[dict]]` | monitor.py:71 | monitor.py, ui_mode.py (via Argument) | monitor.py | Tool-Calls pro Agent für UI |
| `_last_monitored_count` | `Optional[int]` | monitor.py:72 | monitor.py | monitor.py | Logging-Guard: Session-Count |
| `hook_log_position` | `int` | monitor.py:73 | monitor.py | monitor.py | Byte-Offset im Hook-Log |
| `pending_pretooluse_hooks` | `Dict[str, dict]` | monitor.py:74 | monitor.py | monitor.py | Wartende PreToolUse-Hook-Outputs |
| `pending_user_prompt_hook` | `Optional[dict]` | monitor.py:75 | monitor.py | monitor.py | Wartender UserPromptSubmit-Output |
| `active_rules` | `Dict[str, set]` | monitor.py:76 | monitor.py, ui_mode.py (via Argument) | monitor.py | Aktive Regeln nach Scope |
| `warned_unknown_types` | `Set[str]` | monitor.py:77 | monitor.py | monitor.py | Bereits gewarnted unknown Types |
| `unknown_type_counts` | `Dict[str, int]` | monitor.py:78 | monitor.py | monitor.py | Count pro unbekanntem Type |

**Kopplungsanalyse:** `agent_to_task`, `agent_to_type`, `subagent_metadata`, `tool_calls_by_agent`, `active_rules` werden als Argumente an `run_ui_loop()` (ui_mode.py:31) übergeben und dort auch von `track_subagent_metadata()` (ui_mode.py:85) geschrieben. De-facto shared mutable state, nur formal als Argument übergeben.

### buffered_subagent_calls — kein TTL (Kategorie: Memory)

`buffered_subagent_calls: Dict[str, List[dict]]` (monitor.py:65):
- Eintrag wird hinzugefügt wenn Subagent-Call eintrifft, aber `agent_id` noch nicht in `agent_to_task` ist (`handle_subagent_call()`, monitor.py:410-414)
- Eintrag wird geleert wenn Task-Response mit `spawned_agent_id` eintrifft (`handle_task_response()`, monitor.py:374-379)
- Kein TTL: Wenn keine Task-Response eintrifft (z.B. Claude Code crashed, Session endet), wachsen Einträge unbegrenzt
- Kein Cleanup bei Session-Removal (anders als `tool_use_caches` die via `update_session_tracking()` bereinigt werden)

### Unknown Type Tracking (Kategorie: Format-Stabilität)

`unknown_type_counts: Dict[str, int]` (monitor.py:78) und `warned_unknown_types: Set[str]` (monitor.py:77):
- `detect_unknown_types()` in jsonl_parser.py erkennt Message Types die nicht in KNOWN_MESSAGE_TYPES oder KNOWN_IGNORED_TYPES sind
- `track_unknown_type()` in monitor.py akkumuliert Counts
- `format_warnings_block()` rendert Warnings für dediziertes tmux Pane
- `run_warnings_loop()` pollt und rendert wie run_rules_loop()

### Hook Routing — pending State (Kategorie: Korrektheit)

`pending_pretooluse_hooks: Dict[str, dict]` (monitor.py:74) keyed by `tool_name`:
- Eintrag hinzugefügt in `process_hook_log()` (monitor.py:452-455) wenn PreToolUse-Hook-Output vorhanden
- Eintrag konsumiert in `display_tool_call()` (monitor.py:270): `pending_pretooluse_hooks.pop(tool_name, None)`
- Überschreibt vorherigen Eintrag für denselben Tool-Namen ohne Warnung (mehrere PreToolUse-Hooks für dasselbe Tool möglich)

`pending_user_prompt_hook: Optional[dict]` (monitor.py:75):
- Immer nur ein Eintrag gleichzeitig
- Neuer Hook-Output überschreibt alten (monitor.py:449: `pending_user_prompt_hook = entry`)

### Logging im Core Loop (Kategorie: Observability)

`src/monitor.py`: ~15 `log_tagged()`-Aufrufe → `src/logs/02_initialization.log`, `03_session_discovery.log`, `04_file_reading.log`, `07_display_routing.log`
Tags: RUN_MONITOR, RULES_MODE, UI_MODE, STREAM_MODE, INIT_SESS, FILE_POS_INIT, HOOK_POS_INIT, MON_SESS, NEW_SESS, SESS_REMOVED, HOOK_ATTACHED, PROC_STATS, USER_PROMPT, HOOK_PENDING_UP, HOOK_PENDING

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- (keine)

## Quellen

- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: Token counts ~2x too low in JSONL (betrifft `turn_usage_accumulator`)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
