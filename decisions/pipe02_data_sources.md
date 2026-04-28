# Pipe Section: Data Sources

## Status Quo

- `session_finder.py`: `~/.claude/projects/` → glob `*.jsonl` + `*/subagents/agent-*.jsonl`, sorted by mtime
- `jsonl_parser.py`: tool_use/tool_result correlation via cache, extracts 9 data types (tools, prompts, media, thinking, skills, warnings, usage, unknown_types) via 9-Tuple-Rückgabe
- `hook_parser.py`: reads `src/logs/hook_outputs.jsonl`, filters by project cwd — generisch, kein Event-Typ-Filter
- External pipeline: `instructions-loaded-hook.sh` + `session-start-rules.sh` (native hooks in `~/.claude/settings.json`) → `hook_logger.py` → `hook_outputs.jsonl`
- `constants.py`: `KNOWN_MESSAGE_TYPES = {'assistant', 'user', 'progress', 'system', 'result'}`, `KNOWN_IGNORED_TYPES = {'file-history-snapshot', 'queue-operation', 'last-prompt', 'custom-title', 'agent-name', 'attachment', 'permission-mode'}`
- `constants.py`: 25 Hook-Event-Konstanten (`HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_POST_TOOL`, `HOOK_POST_TOOL_FAILURE`, `HOOK_PERMISSION_REQUEST`, `HOOK_PERMISSION_DENIED`, `HOOK_SUBAGENT_START`, `HOOK_SUBAGENT_STOP`, `HOOK_TEAMMATE_IDLE`, `HOOK_TASK_CREATED`, `HOOK_TASK_COMPLETED`, `HOOK_STOP`, `HOOK_STOP_FAILURE`, `HOOK_FILE_CHANGED`, `HOOK_CWD_CHANGED`, `HOOK_CONFIG_CHANGE`, `HOOK_PRE_COMPACT`, `HOOK_POST_COMPACT`, `HOOK_ELICITATION`, `HOOK_ELICITATION_RESULT`, `HOOK_NOTIFICATION`, `HOOK_WORKTREE_CREATE`, `HOOK_WORKTREE_REMOVE` + bestehende 3) und `HOOK_EVENT_CATEGORIES` Dict für Color-Mapping
- `jsonl_parser.py`: `detect_unknown_types()` scannt Messages gegen `KNOWN_MESSAGE_TYPES | KNOWN_IGNORED_TYPES` und gibt unbekannte Types zurück → Warnings-Pane
- `jsonl_parser.py`: `extract_system_messages()` extrahiert `type=system` Messages und deren Text-Content; Rückgabe als 10. Element des Parse-Tuples
- `session-start-rules.sh`: liest stdin (JSON mit `source`, `cwd`), logt via `hook_logger.py` mit `source=$SOURCE`; nutzt `$CWD` aus JSON statt `$(pwd)` für Worktree-Check

*(Removed 2026-04-28: hook_parser.py, rules_pane.py, hooks_pane.py, hooks_format.py, hooks_persist.py, ui_mode.py — the entire hook-log pipeline and rules/hooks panes were deleted. Window 2 (rules+hooks) removed; monitor is now 4 windows.)*

## IST — Stellschrauben

### Session Discovery — Filesystem-Scan pro Poll (Kategorie: Performance)

`find_active_sessions()` in `src/session_finder.py:25-36` wird jeden Poll-Zyklus (alle 0.5s) aufgerufen. Ablauf pro Aufruf:
1. `get_project_directories()` (session_finder.py:41-54): `CLAUDE_PROJECTS_DIR.iterdir()` — liest gesamtes `~/.claude/projects/` Directory
2. `collect_jsonl_files()` (session_finder.py:57-73): Pro Projekt-Dir zwei Globs:
   - `project_dir.glob('*.jsonl')` — Session-Dateien
   - `project_dir.glob('*/subagents/agent-*.jsonl')` — Subagent-Dateien
3. `sort_by_modification_time()` (session_finder.py:87-88): `sorted(..., key=lambda f: f.stat().st_mtime, reverse=True)` — `stat()` Syscall pro Datei

Kein Caching zwischen Polls. Bei vielen Projekten/Sessions: O(N) Syscalls pro 0.5s.
`CLAUDE_PROJECTS_DIR` ist hardcoded: `Path.home() / '.claude' / 'projects'` (session_finder.py:18).

### JSONL Parsing — 5 separate Iterationen (Kategorie: Performance)

`parse_new_tool_calls()` in `src/jsonl_parser.py:35-53` iteriert die `messages`-Liste 5x:
1. `extract_tool_calls(messages, tool_use_cache)` — tool_use/tool_result Paare (jsonl_parser.py:43)
2. `extract_user_prompts(messages)` — externe User-Prompts (jsonl_parser.py:44)
3. `extract_user_media(messages)` — Bilder, Dokumente (jsonl_parser.py:45)
4. `extract_thinking_blocks(messages)` — Thinking-Blöcke (jsonl_parser.py:46)
5. `extract_skill_activations(messages)` — Skill/Command-Aktivierungen (jsonl_parser.py:47)

Jede Funktion iteriert vollständig über alle Messages. Keine gemeinsame Iteration mit Switch-Dispatch.

**9-Tuple-Rückgabe und Erweiterbarkeit:**
`parse_new_tool_calls()` gibt zurück:
`(tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, usage_data)`

`extract_usage_data()` extrahiert pro assistant-Message: `output_tokens`, `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, Content-Block-Type (thinking/tool_use/text), Tool-Name (bei tool_use), `requestId`. Rückgabe: `[{type, tool_name, output_tokens, input_tokens, cache_creation_input_tokens, cache_read_input_tokens, request_id}]`. Filter: Skip wenn BEIDE output_tokens UND input_tokens == 0.

Jedes neue JSONL-Datenformat erfordert:
1. Neue `extract_*()`-Funktion
2. Neuer Rückgabewert im 9-Tuple
3. Neues Entpacken in `process_session_file()` (monitor.py)
4. Neue Display-Funktion in monitor.py
5. Ggf. neuer Eintrag in KNOWN_IGNORED_TYPES (constants.py)

Das Tuple wächst linear mit der Anzahl extrahierter Datentypen.

### tool_use_cache — kein Orphan-Cleanup (Kategorie: Memory)

`tool_use_caches: Dict[Path, dict]` in monitor.py:61 — pro Session-Datei ein Cache-Dict.
Der Cache pro Datei (`cache` in `extract_tool_calls()`, jsonl_parser.py:124) ist ein `dict` keyed by `tool_use_id`:
- Eintrag wird bei `tool_use`-Block hinzugefügt (jsonl_parser.py:162): `tool_use_cache[tool_data['tool_use_id']] = tool_data`
- Eintrag wird bei passendem `tool_result` gelöscht (jsonl_parser.py:178): `del tool_use_cache[tool_use_id]`
- Kein TTL, kein Cleanup für Orphaned Entries (tool_use ohne zugehöriges tool_result)

Auswirkung: Wenn Claude Code crashed oder ein Tool-Call nie ein Result bekommt, wächst der Cache unbegrenzt. Wird bei Session-Removal via `del tool_use_caches[removed_file]` (monitor.py:159) vollständig geleert.

### EXCLUDED_TOOLS — einziger Filterpunkt (Kategorie: Konfiguration)

`EXCLUDED_TOOLS = {'Edit'}` in `src/constants.py:18`.
Angewendet in `filter_excluded_tools()` (jsonl_parser.py:258-259), aufgerufen am Ende von `extract_tool_calls()` (jsonl_parser.py:186).
Nur ein einziger Tool-Name ausgeschlossen. Kein Wildcard-Pattern, kein Category-Filter.

### Byte-Offset Tracking — kein Truncation-Handling (Kategorie: Robustheit)

`read_new_lines()` in `src/jsonl_parser.py:71-91`:
- `f.seek(last_position)` (jsonl_parser.py:77) — springt direkt zum gespeicherten Byte-Offset
- Neuer Position nach Lesen: `filepath.stat().st_size` (jsonl_parser.py:95)
- Kein Handling wenn `file_size < last_position` (z.B. bei JSONL-Rotation oder File-Truncation durch Claude Code)

Im Truncation-Fall würde `seek()` ans Dateiende springen und `f.read()` leeren String zurückgeben — kein Error, aber stille Datenverlust.

### Content Polymorphism (Kategorie: Format-Stabilität)

Zwei Stellen handhaben `content` als String oder Array:
- `extract_user_prompts()` (jsonl_parser.py:308-320): `isinstance(content, list)` → text-Blöcke konkatenieren; `isinstance(content, str)` → direkt verwenden
- `extract_result_content()` (jsonl_parser.py:239-245): `isinstance(content, list)` → erstes Element; `str(content)` als Fallback

Kein explizites Format-Versioning. `detect_unknown_types(messages)` in jsonl_parser.py scannt Messages gegen KNOWN_MESSAGE_TYPES | KNOWN_IGNORED_TYPES (constants.py) und meldet unbekannte Types.

### Logging in Data Sources (Kategorie: Observability)

**Stand nach Session 3 (Logging-Entfernung):**

`src/jsonl_parser.py`: **0** `log_tagged()`-Aufrufe. Alle ~14 ehemaligen Calls (`04_file_reading.log`, `05_jsonl_parsing.log`, `06_tool_extraction.log`) wurden entfernt. Kein `import logging` mehr im Modul.

`src/session_finder.py`: **0** `log_tagged()`-Aufrufe. Alle 4 ehemaligen Calls (`03_session_discovery.log`) wurden entfernt.

`src/hook_parser.py`: **0** `log_tagged()`-Aufrufe. Alle 2 ehemaligen Calls (`11_hook_parsing.log`) wurden entfernt.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- InstructionsLoaded feuert nicht nach compaction (Issue #30973) oder /clear (Issue #31017) — Rules-Pane zeigt nur initial geladene Rules
- ANNAHME: Skill-Aktivierung triggert InstructionsLoaded NICHT (CHANGELOG definiert Scope als CLAUDE.md und .claude/rules/*.md)
- Project `.claude/rules/*.md` werden vom Hook nicht erfasst (Bug #33275) — nur Global Rules + CLAUDE.md feuern
- System Prompt (mit "Contents of" Zeilen) wird NICHT ins Session-JSONL geschrieben — alternative Quelle nötig

## Quellen

- Claude Code #30973: github.com/anthropics/claude-code/issues/30973 (InstructionsLoaded + compaction)
- Claude Code #33275: github.com/anthropics/claude-code/issues/33275 (InstructionsLoaded session_start bug)
- Claude Code #31017: github.com/anthropics/claude-code/issues/31017 (InstructionsLoaded + /clear)
- Claude Code #12151: github.com/anthropics/claude-code/issues/12151 (Plugin hook output bug — nicht betroffen, native Hook)
- Claude Code CHANGELOG L340: InstructionsLoaded added v2.1.64
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: Token counts ~2x too low in JSONL (betrifft `usage`-Felder in tool_use-Messages)
- GitHub unified-cowork JSONL Spec: Community reverse-engineered spec für Cowork audit.jsonl (verwandtes Format, nicht identisch mit Monitor_CC JSONL)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
