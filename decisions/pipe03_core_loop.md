# Pipe Section: Core Loop

## Status Quo

- `monitor.py`: `run_main_loop()` (ehemals `run_streaming_loop()`) ruft `load_historical_main()` auf (setzt neueste Main-Session auf Position 0), trackt `current_main_session` via `_get_newest_main_session()`. Detects session change each poll cycle → clears screen + resets position. Pollt alle 0.5s via `process_hook_log()` + `monitor_sessions()` + `_refresh_strip_cache()` + `render_main_buffer()`
- `monitor.py`: `run_rules_loop()` ruft `load_historical_rules()` auf (liest Hook-Log ab 0, füllt `active_rules`), dann pollt alle 0.5s via `process_hook_log()` und rendert `format_rules_block(active_rules)` bei Änderungen
- `monitor.py`: `run_tokens_loop()` pollt alle 0.5s, `build_cache_turns()` liest neueste Main-Session ab Position 0 und rendert Cache-Tracker. Unterstützt Mouse-Events (Expand/Collapse, Hover).
- `monitor.py`: `run_hooks_loop()` ruft `load_historical_hooks()` auf (liest Hook-Log ab 0, druckt ALLE Entries inkl. ohne Output), dann pollt alle 0.5s via `process_hook_log_for_display()`
- `monitor.py`: `run_warnings_loop()` ruft `load_historical_warnings()` auf (setzt neueste Main-Session auf Position 0), dann pollt alle 0.5s via `monitor_sessions()` und rendert `format_warnings_block()` bei Änderungen
- `monitor.py`: `run_workers_loop()` pollt alle 0.5s, ruft `list_workers()` auf und rendert `format_workers_block()` bei Änderungen. Expanded Workers zeigen Cache-Tracker Token-View (CR/CC/D per API Call) via `extract_cache_turns()` + `format_cache_tracker()`. Keine Subagent-Rendering mehr (separates Pane).
- `monitor.py`: `run_subagents_loop()` pollt alle 0.5s, ruft `monitor_sessions()` auf, lädt per-Agent JSONL via `find_agent_jsonl()`, rendert `render_subagents_with_tokens()` bei Änderungen. Unterstützt Mouse-Events (Expand/Collapse, Scroll, Hover) und Digit-Keys. Session-Reset: detects main session change via `_get_newest_main_session()`, clears all subagent state (metadata, turns, expand/scroll states, subagent_states, file_positions, tool_use_caches), re-runs `load_historical_subagents()`. Scroll fix: `_find_agent_at_row()` walks upward in line_map for scroll events in expanded areas.
- `monitor.py`: `load_historical_subagents()` setzt neueste Main-Session + deren Agent-Files (`filepath.parent/filepath.stem/subagents/agent-*.jsonl`) auf Position 0 (nur aktuelle Session, nicht alle historischen).
- `run_monitor()` routet `MODE_SUBAGENTS` → `run_subagents_loop()`.
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

`run_rules_loop()` Ablauf:
1. `process_hook_log()` → aktualisiert `active_rules`
2. `format_rules_block(active_rules)` → rendert ACTIVE RULES Block
3. Bei Änderung: Screen-Clear + Print
4. `time.sleep(POLL_INTERVAL)`

`run_workers_loop()` Ablauf:
1. `list_workers(active_project_filter)` → liest tmux-Sessions mit `worker-{project}-` Prefix
2. Pro Worker: `detect_worker_status()` via `#{pane_dead}` + pane-content-Analyse, `get_tmux_env()` für WORKER_SPAWNED + WORKER_PURPOSE
3. Pro erweitertem Worker: `find_worker_jsonl()` → `extract_cache_turns()` → `worker_turns[name]`
4. `format_workers_block(workers, expand_states, worker_turns, ...)` → rendert Worker-Liste mit Cache-Tracker bei Expand
5. Bei Änderung: Screen-Clear + Print
6. `time.sleep(POLL_INTERVAL)`

## IST — Stellschrauben

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
| `active_mode` | `str` | monitor.py:36 | monitor.py | monitor.py | Aktueller Mode (all/main/subagent/rules/...) |
| `ui_mode_active` | `bool` | monitor.py:37 | monitor.py | monitor.py | Flag: UI-Mode aktiv |
| `subagent_metadata` | `Dict[str, dict]` | monitor.py:38 | monitor.py, ui_mode.py (via Argument) | monitor.py | Subagent-Metadaten für UI |
| `tool_calls_by_agent` | `Dict[str, List[dict]]` | monitor.py:39 | monitor.py, ui_mode.py (via Argument) | monitor.py | Tool-Calls pro Agent für UI |
| `_last_monitored_count` | `Optional[int]` | monitor.py:40 | monitor.py | monitor.py | Logging-Guard: Session-Count |
| `hook_log_position` | `int` | monitor.py:41 | monitor.py | monitor.py | Byte-Offset im Hook-Log |
| `active_rules` | `Dict[str, set]` | monitor.py:42 | monitor.py, ui_mode.py (via Argument) | monitor.py | Aktive Regeln nach Scope |
| `warned_unknown_types` | `Set[str]` | monitor.py:43 | monitor.py | monitor.py | Bereits gewarnted unknown Types |
| `unknown_type_counts` | `Dict[str, int]` | monitor.py:44 | monitor.py | monitor.py | Count pro unbekanntem Type |
| `token_profile` | `Dict[str, int]` | monitor.py:45 | monitor.py | monitor.py | Kumulative Output-Tokens nach Block-Type |
| `token_profile_tools` | `Dict[str, int]` | monitor.py:46 | monitor.py | monitor.py | Output-Tokens nach Tool-Name |
| `token_profile_request_ids` | `Set[str]` | monitor.py:47 | monitor.py | monitor.py | Gesehene requestIds (Turn-Dedup) |
| `token_cumulative_n` | `Optional[int]` | monitor.py:48 | monitor.py | monitor.py | Session-Browser: letzte N Sessions (None = current session) |
| `token_input_buffer` | `str` | monitor.py:49 | monitor.py | monitor.py | Keyboard-Input-Buffer für Session-Browser |

**Entfernt in Session 2/3:** `pending_pretooluse_hooks` und `pending_user_prompt_hook` wurden als Teil der Hook-Routing-Vereinfachung entfernt. `process_hook_log()` bufferiert keine PreToolUse/UserPromptSubmit-Outputs mehr.

**Kopplungsanalyse:** `agent_to_task`, `agent_to_type`, `subagent_metadata`, `tool_calls_by_agent`, `active_rules` werden als Argumente an `run_ui_loop()` (ui_mode.py:19) übergeben und dort auch von `track_subagent_metadata()` (ui_mode.py:72) geschrieben. De-facto shared mutable state, nur formal als Argument übergeben.

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

### Hook Routing — vereinfacht (Kategorie: Korrektheit)

**Stand nach Session 2/3:** `pending_pretooluse_hooks` und `pending_user_prompt_hook` wurden entfernt.

`process_hook_log()` (monitor.py:687-699) verarbeitet jetzt NUR noch `InstructionsLoaded`:
- Alle anderen Hook-Events werden ignoriert (nicht gebuffert, nicht angezeigt)
- `[P]` Prefix → `active_rules['project'].add(...)`
- `[G]` Prefix → `active_rules['global'].add(...)`

`process_hook_log_for_display()` (monitor.py:651-668) ist der separate Code-Pfad für die Hooks-Pane:
- Verarbeitet ALLE Hook-Events mit Output (kein Typ-Filter)
- Zeigt Output sofort als scrolling stream an (kein State, kein Buffering)
- Hooks ohne Output werden gefiltert (`if not output: continue`)

### Logging im Core Loop (Kategorie: Observability)

**Stand nach Session 3 (Logging-Entfernung):**

`src/monitor.py`: **0** `log_tagged()`-Aufrufe. Alle ~15 ehemaligen Calls (RUN_MONITOR, RULES_MODE, UI_MODE, STREAM_MODE, INIT_SESS, FILE_POS_INIT, HOOK_POS_INIT, MON_SESS, NEW_SESS, SESS_REMOVED, HOOK_ATTACHED, PROC_STATS, USER_PROMPT, HOOK_PENDING_UP, HOOK_PENDING) wurden entfernt. Kein `import logging` mehr in monitor.py.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

### filter_sessions_by_mode — Session Count im Header (Session 4, Kategorie: Korrektheit)

`run_monitor()` (monitor.py:52-79) ruft jetzt `filter_sessions_by_mode(sessions, mode)` auf, BEVOR es `print_session_status(session_count, ...)` aufruft (monitor.py:72-73 und 77-78).

Vorher: `session_count = len(sessions)` — zählte alle Sessions (main + subagent) unabhängig vom Mode
Jetzt: `session_count = len(filter_sessions_by_mode(sessions, mode))` — zählt nur die tatsächlich im jeweiligen Mode relevanten Sessions

Betrifft Modes: `MODE_MAIN` (nur Non-Agent-Files), `MODE_SUBAGENT` (nur Agent-Files), `MODE_ALL` (alle).

## Offene Fragen

- `buffered_subagent_calls` hat noch keinen TTL-Cleanup (bleibt offen)

## Quellen

- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: Token counts ~2x too low in JSONL (betrifft `turn_usage_accumulator`)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
