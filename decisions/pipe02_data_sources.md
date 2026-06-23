# Pipe Section: Data Sources

## Status Quo (IST)

- `session_finder.py`: `~/.claude/projects/` → glob `*.jsonl` + `*/subagents/agent-*.jsonl`, sorted by mtime
- `jsonl_parser.py`: tool_use/tool_result correlation via cache, extracts 8 data types (tools, prompts, media, thinking, skills, warnings, usage, system) via 9-Tuple-Rückgabe
- `constants.py`: 25 Hook-Event-Konstanten (`HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_POST_TOOL`, `HOOK_POST_TOOL_FAILURE`, `HOOK_PERMISSION_REQUEST`, `HOOK_PERMISSION_DENIED`, `HOOK_SUBAGENT_START`, `HOOK_SUBAGENT_STOP`, `HOOK_TEAMMATE_IDLE`, `HOOK_TASK_CREATED`, `HOOK_TASK_COMPLETED`, `HOOK_STOP`, `HOOK_STOP_FAILURE`, `HOOK_FILE_CHANGED`, `HOOK_CWD_CHANGED`, `HOOK_CONFIG_CHANGE`, `HOOK_PRE_COMPACT`, `HOOK_POST_COMPACT`, `HOOK_ELICITATION`, `HOOK_ELICITATION_RESULT`, `HOOK_NOTIFICATION`, `HOOK_WORKTREE_CREATE`, `HOOK_WORKTREE_REMOVE` + bestehende 3) und `HOOK_EVENT_CATEGORIES` Dict für Color-Mapping- `jsonl_parser.py`: `extract_system_messages()` extrahiert `type=system` Messages und deren Text-Content; Rückgabe als 9. (letztes) Element des 9-Tuples
- `session-start-rules.sh`: liest stdin (JSON mit `source`, `cwd`), logt via `hook_logger.py` mit `source=$SOURCE`; nutzt `$CWD` aus JSON statt `$(pwd)` für Worktree-Check (NOTE: Dateiname stale — nicht im Repo vorhanden; gegen tatsächlichen Global-Hook verifizieren, vgl. `session-start-project-rules.sh`)


### Session Discovery — Filesystem-Scan pro Poll (Kategorie: Performance)

`find_active_sessions()` in `src/session_finder.py:16-26` wird jeden Poll-Zyklus (alle 0.5s) aufgerufen. Ablauf pro Aufruf:
1. `get_project_directories()` (session_finder.py:31-42): `CLAUDE_PROJECTS_DIR.iterdir()` — liest gesamtes `~/.claude/projects/` Directory
2. `collect_jsonl_files()` (session_finder.py:45-60): Pro Projekt-Dir zwei Globs:
   - `project_dir.glob('*.jsonl')` — Session-Dateien
   - `project_dir.glob('*/subagents/agent-*.jsonl')` — Subagent-Dateien
3. `sort_by_modification_time()` (session_finder.py:74-76): `sorted(..., key=lambda f: f.stat().st_mtime, reverse=True)` — `stat()` Syscall pro Datei

Kein Caching zwischen Polls. Bei vielen Projekten/Sessions: O(N) Syscalls pro 0.5s.
`CLAUDE_PROJECTS_DIR` ist hardcoded: `Path.home() / '.claude' / 'projects'` (session_finder.py:9).

### JSONL Parsing — 7 separate Iterationen (Kategorie: Performance)

`parse_new_tool_calls()` in `src/jsonl/jsonl_parser.py:75-87` iteriert die `messages`-Liste 7x:
1. `extract_tool_calls(messages, tool_use_cache)` — tool_use/tool_result Paare (jsonl_parser.py:79)
2. `extract_user_prompts(messages)` — externe User-Prompts (jsonl_parser.py:80)
3. `extract_user_media(messages)` — Bilder, Dokumente (jsonl_parser.py:81)
4. `extract_thinking_blocks(messages)` — Thinking-Blöcke (jsonl_parser.py:82)
5. `extract_skill_activations(messages)` — Skill/Command-Aktivierungen (jsonl_parser.py:83)
6. `extract_usage_data(messages)` — Token-Usage pro assistant-Message (jsonl_parser.py:84)
7. `extract_system_messages(messages)` — type=system Messages (jsonl_parser.py:85)

Jede Funktion iteriert vollständig über alle Messages. Keine gemeinsame Iteration mit Switch-Dispatch.

**9-Tuple-Rückgabe und Erweiterbarkeit:**
`parse_new_tool_calls()` gibt zurück:
`(tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, usage_data, system_messages)`

`extract_usage_data()` extrahiert pro assistant-Message: `output_tokens`, `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, Content-Block-Type (thinking/tool_use/text), Tool-Name (bei tool_use), `requestId`. Rückgabe: `[{type, tool_name, output_tokens, input_tokens, cache_creation_input_tokens, cache_read_input_tokens, request_id}]`. Filter: Skip wenn BEIDE output_tokens UND input_tokens == 0.

Jedes neue JSONL-Datenformat erfordert:
1. Neue `extract_*()`-Funktion
2. Neuer Rückgabewert im 9-Tuple
3. Neues Entpacken in `process_session_file()` (core/monitor_session.py)
4. Neue Display-Funktion (panes/ bzw. core/monitor.py)

Das Tuple wächst linear mit der Anzahl extrahierter Datentypen.

### tool_use_cache — kein Orphan-Cleanup (Kategorie: Memory)

`tool_use_caches: Dict[Path, dict]` in core/monitor.py:30 — pro Session-Datei ein Cache-Dict.
Der Cache pro Datei (`cache` in `extract_tool_calls()`, jsonl_parser.py:141) ist ein `dict` keyed by `tool_use_id`:
- Eintrag wird bei `tool_use`-Block hinzugefügt (jsonl_parser.py:176): `tool_use_cache[tool_data['tool_use_id']] = tool_data`
- Eintrag wird bei passendem `tool_result` gelöscht (jsonl_parser.py:187): `del tool_use_cache[tool_use_id]`
- Kein TTL, kein Cleanup für Orphaned Entries (tool_use ohne zugehöriges tool_result)

Auswirkung: Wenn Claude Code crashed oder ein Tool-Call nie ein Result bekommt, wächst der Cache unbegrenzt. Wird bei Session-Removal via `del tool_use_caches[removed_file]` (core/monitor.py:113) vollständig geleert.

### EXCLUDED_TOOLS — einziger Filterpunkt (Kategorie: Konfiguration)

`EXCLUDED_TOOLS = {'Edit'}` in `src/constants.py:121`.
Angewendet in `filter_excluded_tools()` (jsonl_parser.py:251-252), aufgerufen am Ende von `extract_tool_calls()` (jsonl_parser.py:191).
Nur ein einziger Tool-Name ausgeschlossen. Kein Wildcard-Pattern, kein Category-Filter.

### Byte-Offset Tracking — kein Truncation-Handling (Kategorie: Robustheit)

`read_new_lines()` in `src/jsonl/jsonl_parser.py:105-116`:
- `f.seek(last_position)` (jsonl_parser.py:109) — springt direkt zum gespeicherten Byte-Offset
- Neuer Position nach Lesen: `filepath.stat().st_size` (jsonl_parser.py:120)
- Kein Handling wenn `file_size < last_position` (z.B. bei JSONL-Rotation oder File-Truncation durch Claude Code)

Im Truncation-Fall würde `seek()` ans Dateiende springen und `f.read()` leeren String zurückgeben — kein Error, aber stille Datenverlust.

### Content Polymorphism (Kategorie: Format-Stabilität)

Zwei Stellen handhaben `content` als String oder Array:
- `extract_user_prompts()` (jsonl_extractors.py:30-63): `isinstance(content, list)` → text-Blöcke konkatenieren; `isinstance(content, str)` → direkt verwenden
- `extract_result_content()` (jsonl_parser.py:242-248): `isinstance(content, list)` → erstes Element; `str(content)` als Fallback

Kein explizites Format-Versioning.


## Evidenz

### Session Discovery I/O (IST-1)

`dev/pipeline/io_profile/01_reports/poll_cycle_20260322_152817.md` (Script: `dev/pipeline/io_profile/01_poll_cycle_cost.py`, Dataset: 70 Projekte, 1479 JSONL-Dateien in `~/.claude/projects/`, 2026-03-22):

- Ohne Project-Filter: Cycle-Duration **9.58ms** (±0.99), **1479 stat()-Calls**, 140 glob()-Calls pro Zyklus
- Mit Project-Filter (Monitor_CC): **0.25ms** (±0.05), 0 stat()-Calls
- Filterung reduziert Zyklus-Overhead um 9.33ms (97%)

### JSONL Multi-Pass Parsing (IST-2)

`dev/pipeline/parsing_profile/01_reports/multipass_20260322_152816.md` (Script: `dev/pipeline/parsing_profile/01_multipass_cost.py`, Dataset: Session `35ca8892`, 351 Messages, 10 Messläufe):

| Funktion | Mean (µs) | % |
|---|---|---|
| `extract_tool_calls` | 1773.6 | 93.6% |
| `extract_skill_activations` | 39.9 | 2.1% |
| `extract_user_prompts` | 37.3 | 2.0% |
| `extract_thinking_blocks` | 26.9 | 1.4% |
| `extract_user_media` | 17.8 | 0.9% |
| **Total (5 Passes)** | **1895.5** | 100% |

Average 5.40 µs/Message. Single-pass savings estimate: 70.2 µs.

Scope-Hinweis: Diese Messung erfasste **5 Passes (pre-refactor)** — vor Hinzufügen von `extract_usage_data` + `extract_system_messages`. Die 2 zusätzlichen Passes sind leichtgewichtig (analog `extract_user_media`/`extract_thinking_blocks` <1% Anteil). Der IST-Pass-Count ist aktuell **7** (siehe oben).

### tool_use_cache Orphan-Verhalten (IST-3)

`dev/pipeline/memory_profile/01_reports/cache_growth_20260322_152818.md` (Script: `dev/pipeline/memory_profile/01_cache_growth.py`, Dataset: Session `35ca8892`, 357 Messages):
- Peak cache entries: 1; Final orphaned: **1** (Bash-Call ohne zugehöriges tool_result)
- Estimated memory per 1000 messages: 515 bytes

### Format-Stabilität / Unknown Types (IST-7)

`dev/pipeline/format_stability/01_reports/unknown_types_20260322_152802.md` (Script: `dev/pipeline/format_stability/01_unknown_types.py`, Dataset: **1479 JSONL-Dateien**, 222,636 Lines, 52 Parse-Errors, 2026-03-22):
- Known top-level type coverage: **91.9%**
- 5 unknown top-level types: `file-history-snapshot`, `queue-operation`, `last-prompt`, `custom-title`, `agent-name`
- Unknown content-block types: **0** (100% bekannt)

IST-4 (`EXCLUDED_TOOLS`), IST-5 (Truncation-Handling), IST-6 (Content Polymorphism), IST-8 (Logging 0) sind code-read-derived — kein dev/-Benchmark backing.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- InstructionsLoaded feuert nicht nach compaction (Issue #30973) oder /clear (Issue #31017) — Rules-Pane zeigt nur initial geladene Rules
- ANNAHME: Skill-Aktivierung triggert InstructionsLoaded NICHT (CHANGELOG definiert Scope als CLAUDE.md und project-rules-Dateien)
- Project-rules-Dateien werden vom Hook nicht erfasst (Bug #33275) — nur Global Rules + CLAUDE.md feuern
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
