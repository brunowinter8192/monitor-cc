# Pipe Section: Core Loop

## Status Quo (IST)

- `monitor.py`: `run_main_loop()` (ehemals `run_streaming_loop()`) ruft `load_historical_main()` auf (setzt neueste Main-Session auf Position 0), trackt `current_main_session` via `_get_newest_main_session()`. Detects session change each poll cycle → clears screen + resets position. Pollt alle 0.5s via `monitor_sessions()` + `_refresh_strip_cache()` + `render_main_buffer()`
- `monitor.py`: `run_tokens_loop()` pollt alle 0.5s, `build_cache_turns()` liest neueste Main-Session ab Position 0 und rendert Cache-Tracker. Unterstützt Mouse-Events (Expand/Collapse, Hover).
- `monitor.py`: `run_warnings_loop()` ruft `load_historical_warnings()` auf (setzt neueste Main-Session auf Position 0), dann pollt alle 0.5s via `monitor_sessions()` und rendert `format_warnings_block()` bei Änderungen
- *(Removed 2026-04-28: `run_rules_loop()`, `run_hooks_loop()`, `process_hook_log()`, `process_hook_log_for_display()`, `initialize_hook_log_position()`, `hook_log_position` state — entire hook-log pipeline and rules/hooks panes deleted. Window 2 removed, monitor is now 4 windows.)*
- `monitor.py`: `run_workers_loop()` pollt alle 0.5s, ruft `list_workers()` auf und rendert `format_workers_block()` bei Änderungen. Expanded Workers zeigen Cache-Tracker Token-View (CR/CC/D per API Call) via `extract_cache_turns()` + `format_cache_tracker()`. Keine Subagent-Rendering mehr (separates Pane).
- Hook routing in `process_hook_log()`: nur noch 1 Event → 1 State Dict
  - `InstructionsLoaded` → `active_rules` (via `[P]`/`[G]` Prefix-Routing)
  - Alle anderen Hook-Events → `process_hook_log_for_display()` (Hooks-Pane, kein State)
  - `UserPromptSubmit` und `PreToolUse` werden nicht mehr gebuffert (Buffering in Session 2/3 entfernt)
- `format_hook_event()` in formatter.py: color-coded per `HOOK_EVENT_CATEGORIES` aus constants.py (session=WHITE, agent=BLUE, context=ORANGE, mcp=CYAN, file=DIM, etc.)
- `system_messages` wird als 10. Return-Wert von `parse_new_tool_calls()` zurückgegeben; `process_session_file()` entpackt und rendert via `display_system_message()` / `format_system_message()`
- `process_hook_log_for_display()` (separater Code-Pfad für Hooks-Pane): zeigt ALLE Hook-Events an (mit und ohne Output); Events ohne Output als One-Liner (`[HH:MM:SS] EventType | script_name`), Events mit Output mit Einrückung
- Agent tracking: `agent_to_task`, `agent_to_type` maps, `buffered_subagent_calls` für Orphans (Calls ohne bekannten Agent)
- Token profiling: `accumulate_tokens()` aggregiert Output-Tokens nach Block-Type (thinking/tool_use/text) und Tool-Name in `token_profile` + `token_profile_tools` Globals. Turn-Count via `token_profile_request_ids` Set (dedupliziert `requestId`s). Session-Isolation via file-level Byte-Offsets (nicht 5h-Filter).
- Session-Browser: `token_cumulative_n: Optional[int]` (monitor.py:48) steuert Modus. Keyboard-Input in `run_tokens_loop()`: Ziffern → buffer, Enter → set/clear n, 'q' → clear. `compute_cumulative_tokens(n)` liest letzte N Main-Sessions von Position 0.

`run_workers_loop()` Ablauf:
1. `list_workers(active_project_filter)` → liest tmux-Sessions mit `worker-{project}-` Prefix
2. Pro Worker: `detect_worker_status()` via `#{pane_dead}` + pane-content-Analyse, `get_tmux_env()` für WORKER_SPAWNED + WORKER_PURPOSE
3. Pro erweitertem Worker: `find_worker_jsonl()` → `extract_cache_turns()` → `worker_turns[name]`
4. `format_workers_block(workers, expand_states, worker_turns, ...)` → rendert Worker-Liste mit Cache-Tracker bei Expand
5. Bei Änderung: Screen-Clear + Print
6. `time.sleep(POLL_INTERVAL)`

### Globale Mutable State — alle Variablen (Kategorie: Architektur / Kopplung)

Alle Module-Level Variablen in `src/monitor.py` mit Zugriffs-Mapping (Stand nach Session 3):

| Variable | Typ | Definiert | Gelesen | Geschrieben | Beschreibung |
|----------|-----|-----------|---------|-------------|--------------|
| `file_positions` | `Dict[Path, int]` | monitor.py:28 | monitor.py | monitor.py | Byte-Offsets pro JSONL-Datei |
| `tool_use_caches` | `Dict[Path, dict]` | monitor.py:29 | monitor.py | monitor.py | tool_use_cache pro Session-Datei |
| `call_counter` | `int` | monitor.py:30 | monitor.py | monitor.py | Globaler Call-Zähler für Display |
| `agent_to_task` | `Dict[str, str]` | monitor.py:31 | monitor.py, ui_mode.py (via Argument) | monitor.py | agent_id → task tool_use_id |
| `agent_to_type` | `Dict[str, str]` | monitor.py:32 | monitor.py, ui_mode.py (via Argument) | monitor.py | agent_id → subagent_type |
| `buffered_subagent_calls` | `Dict[str, List[dict]]` | monitor.py:33 | monitor.py | monitor.py | Calls ohne bekannten Agent, kein TTL |
| `task_requests_seen` | `Set[str]` | monitor.py:34 | monitor.py | monitor.py | Gesehene Task-Request IDs |
| `active_project_filter` | `Optional[str]` | monitor.py:35 | monitor.py | monitor.py | Aktiver Projekt-Filter |
| `active_mode` | `str` | monitor.py | monitor.py | monitor.py | Aktueller Mode (all/main/rules/workers/proxy/...) |
| `_last_monitored_count` | `Optional[int]` | monitor.py | monitor.py | monitor.py | Logging-Guard: Session-Count |
| `warned_unknown_types` | `Set[str]` | monitor.py:43 | monitor.py | monitor.py | Bereits gewarnted unknown Types |
| `unknown_type_counts` | `Dict[str, int]` | monitor.py:44 | monitor.py | monitor.py | Count pro unbekanntem Type |
| `token_profile` | `Dict[str, int]` | monitor.py:45 | monitor.py | monitor.py | Kumulative Output-Tokens nach Block-Type |
| `token_profile_tools` | `Dict[str, int]` | monitor.py:46 | monitor.py | monitor.py | Output-Tokens nach Tool-Name |
| `token_profile_request_ids` | `Set[str]` | monitor.py:47 | monitor.py | monitor.py | Gesehene requestIds (Turn-Dedup) |
| `token_cumulative_n` | `Optional[int]` | monitor.py:48 | monitor.py | monitor.py | Session-Browser: letzte N Sessions (None = current session) |
| `token_input_buffer` | `str` | monitor.py:49 | monitor.py | monitor.py | Keyboard-Input-Buffer für Session-Browser |

**Entfernt in Session 2/3:** `pending_pretooluse_hooks` und `pending_user_prompt_hook` wurden als Teil der Hook-Routing-Vereinfachung entfernt. `process_hook_log()` bufferiert keine PreToolUse/UserPromptSubmit-Outputs mehr.

**Kopplungsanalyse:** `agent_to_task`, `agent_to_type` (und früher `subagent_metadata`, `tool_calls_by_agent`, `active_rules`) wurden als Argumente an `run_ui_loop()` (ui_mode.py, entfernt mit Subagents-Feature) übergeben — de-facto shared mutable state. `warned_unknown_types`, `unknown_type_counts` leben in `panes/warnings_parse.py`. Token-Profiling-State (`token_profile` etc.) in `panes/token_pane.py`. `active_rules` und `hook_log_position` entfernt 2026-04-28 mit den rules/hooks panes.

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
- `run_warnings_loop()` pollt und rendert per eigenem Poll-Zyklus

### filter_sessions_by_mode — Session Count im Header (Session 4, Kategorie: Korrektheit)

`run_monitor()` (monitor.py:52-79) ruft jetzt `filter_sessions_by_mode(sessions, mode)` auf, BEVOR es `print_session_status(session_count, ...)` aufruft (monitor.py:72-73 und 77-78).

Vorher: `session_count = len(sessions)` — zählte alle Sessions (main + subagent) unabhängig vom Mode
Jetzt: `session_count = len(filter_sessions_by_mode(sessions, mode))` — zählt nur die tatsächlich im jeweiligen Mode relevanten Sessions

Betrifft Modes: `MODE_MAIN` (nur Non-Agent-Files), `MODE_ALL` (alle). `MODE_SUBAGENT` wurde mit dem Subagents-Feature entfernt.

### Logging im Core Loop (Kategorie: Observability)

**Stand nach Session 3 (Logging-Entfernung):**

`src/monitor.py`: **0** `log_tagged()`-Aufrufe. Alle ~15 ehemaligen Calls (RUN_MONITOR, RULES_MODE, UI_MODE, STREAM_MODE, INIT_SESS, FILE_POS_INIT, HOOK_POS_INIT, MON_SESS, NEW_SESS, SESS_REMOVED, HOOK_ATTACHED, PROC_STATS, USER_PROMPT, HOOK_PENDING_UP, HOOK_PENDING) wurden entfernt. Kein `import logging` mehr in monitor.py.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Die `dev/pipeline/`-Suites wurden primär für pipe02-Entscheidungen aufgesetzt; ihre Messergebnisse backen mehrere pipe03-Claims:

### Poll-Overhead pro 0.5s-Zyklus (IST-1 Kontext)

`dev/pipeline/io_profile/01_reports/poll_cycle_20260322_152817.md` (Script: `dev/pipeline/io_profile/01_poll_cycle_cost.py`, Dataset: 70 Projekte, 1479 Dateien, 2026-03-22): Discovery-Overhead 9.58ms pro Zyklus (ohne Filter) vs. 0.25ms (mit Project-Filter). Bestätigt dass POLL_INTERVAL=0.5s mit Project-Filter die dominante Wartezeit bleibt (Discovery 0.25ms << 500ms Sleep).

### tool_use_cache Orphan-Behavior (IST-4 strukturale Evidenz)

`dev/pipeline/memory_profile/01_reports/cache_growth_20260322_152818.md` (Script: `dev/pipeline/memory_profile/01_cache_growth.py`, Dataset: Session `35ca8892`, 357 Messages): 1 Orphaned Entry nach 357 Messages (Bash-Call ohne tool_result). `buffered_subagent_calls`-Sektion nicht im Report — Test-Session enthielt keine Subagents. Struktural analoges Verhalten zu `tool_use_caches`.

### Unknown Types / Warnings Coverage (IST-5)

`dev/pipeline/format_stability/01_reports/unknown_types_20260322_152802.md` (Script: `dev/pipeline/format_stability/01_unknown_types.py`, Dataset: 1479 Dateien, 222,636 Lines, 2026-03-22): 5 real-world unknown top-level types gefunden (8.1% unbekannt ohne Filter). Belegt dass Warnings-Loop reale Fälle detektiert — nicht nur theoretisch.

IST-2 (workers-loop 6-step), IST-3 (state table), IST-6 (`filter_sessions_by_mode`), IST-7 (token profiling globals), IST-8 (logging 0) sind code-read-derived — kein dev/-Benchmark backing.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- `buffered_subagent_calls` hat noch keinen TTL-Cleanup (bleibt offen)

## Quellen

- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: Token counts ~2x too low in JSONL (betrifft `turn_usage_accumulator`)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
