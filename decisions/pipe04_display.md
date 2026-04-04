# Pipe Section: Display

## Status Quo

- `formatter.py`: 21 Funktionen + Workers-Block + Session-Browser, color-coded output (green=main, blue=subagent, red=error, pastel=meta)
- `ui_mode.py`: `format_rules_block()` rendert `ACTIVE RULES (XP / YG)` mit `[P]`/`[G]` Prefix pro Regel, pastel blue
- `subagent_ui.py`: collapsible list, Digits 1-9 toggle via `click_handler.py`, `start_line` param für korrekte line_to_agent_map in kombinierten Panes
- Workers-Pane (Window 2, Pane 2.0): `run_workers_loop()` + `format_workers_block()` — zeigt Worker-Name, Status, Spawn-Zeit, Purpose. Subagents werden darunter gerendert via `render_subagent_list()`.

**BUG (fixed):** `active_rules` was populated by `process_hook_log()` but never rendered in streaming mode.
Fix: `run_rules_loop()` in monitor.py + dedicated `--mode rules` tmux pane (Window 1, Pane 1.0).
**BUG (fixed):** Project `.claude/rules/*.md` did not appear — root cause was YAML array syntax in `paths:` frontmatter (Claude Code Bug #19377/#33581). CSV parser expects string, receives JS Array from `yaml.parse()`, producing broken globs. Fix: CSV string format (`paths: src/**, workflow.py`). All project rules now load correctly via InstructionsLoaded hook.
**BUG (fixed):** Rules-Pane showed historical rules from previous sessions because `hook_log_position` was set to 0 (read from beginning of hook log). Fix: removed `hook_log_position = 0` override, now starts from EOF like all other modes.
**BUG (fixed, Session 12):** Rules-Pane and Hooks-Pane showed data from ALL past sessions (old timestamps, closed-worktree rules, 20000+ historical hook events). Root cause: `load_historical_rules()` and `load_historical_hooks()` read `hook_outputs.jsonl` from position 0 with no timestamp filter; `active_rules` only accumulated, never cleared. Fix:
- `_get_session_start_ts()` reads first `timestamp` from newest main session JSONL → `session_start_ts` global
- `filter_by_timestamp()` added to `hook_parser.py`: ISO 8601 lexicographic comparison filters entries before session start
- `load_historical_rules()`: clears `active_rules` + `rules_invokers` before loading, applies `filter_by_timestamp()`
- `load_historical_hooks()`: applies `filter_by_timestamp()` to suppress pre-session entries
- `run_rules_loop()` and `run_hooks_loop()`: track `current_main_session` via `_get_newest_main_session()`; on session change: update `session_start_ts`, re-run historical load with new timestamp
- Token Pane unaffected (reads session JSONL directly, natural session boundary)

Rules-Pane Layout:
- Window 1 "rules", Pane 1.0 (links 50%): `python3 workflow.py --mode rules` → `run_rules_loop()`
- Rendert `format_rules_block()` bei jeder Änderung von `active_rules`
- M-r Keybinding: Rules-Pane Content → Clipboard via `pbcopy`

## IST — Stellschrauben

### LONG_OUTPUT_THRESHOLD (Kategorie: Display / UX)

`LONG_OUTPUT_THRESHOLD = 10000` in `src/constants.py`.
Verwendet in `format_output()` (formatter.py:119-138):
- `len(content) >= LONG_OUTPUT_THRESHOLD` → `log_long_output(content)` aufgerufen + `LIGHT_RED_BG` Hintergrundfarbe für den gesamten Output-Block
- `log_long_output()` (formatter.py:213-219) schreibt: char_count, line_count, 500-char Preview, und **den vollständigen Content** nach `src/logs/10_long_outputs.log`

Zentralisiert in constants.py.

### Input Preview Truncation (Kategorie: Display / UX)

`get_input_preview()` in `src/subagent_ui.py:159-179`:
- Pro Key-Value-Paar: `value_str[:50] + '...'` wenn `len(value_str) > 50` (subagent_ui.py:170-171)
- Gesamtes Ergebnis: `result[:120] + '...'` wenn `len(result) > 120` (subagent_ui.py:175)
- Fallback für nicht-dict input: `str(input_data)[:40] + '...'` wenn `> 40` (subagent_ui.py:164)

Drei verschiedene Truncation-Schwellen (40, 50, 120), alle hardcoded.

### SCORE_PATTERN Regex (Kategorie: Display / UX)

`SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')` in `src/formatter.py:20`.
Verwendet in `format_output()` (formatter.py:130-131): Zeilen die matchen werden in `GREEN` coloriert.
Speziell für RAG-Suchergebnisse (Format aus rag-Plugin). Hardcoded Pattern.

### Pane Headers (Kategorie: Display / UX)

Sticky headers via tmux `pane-border-status top` + `pane-border-format` in `configure_tmux_session()`. Pane titles set via `select-pane -T` for all 7 panes (MAIN, TOKENS, RULES, HOOKS, WORKERS, WARNINGS, SUBAGENTS). Color: `colour216` (PASTEL_ORANGE). Headers never scroll away — tmux renders them in the pane border.

`format_pane_header()` in formatter.py still exists (PASTEL_ORANGE) but is no longer called from any loop. All header print calls removed from monitor.py and ui_mode.py (Session 6).

### Token-Profiling Pane (Kategorie: Display / Token Visibility)

Eigenes tmux Pane (Window 0 "main", Pane 0.1, rechts 30%) via `--mode tokens`:
- `run_tokens_loop()` in monitor.py: pollt `monitor_sessions()`, akkumuliert via `accumulate_tokens()`, rendert `format_tokens_block()`
- `format_token_profile()` in formatter.py: flat Breakdown (per-tool + Text) mit Unicode Bar-Chart (bar_width=30) und Prozentwerten. Color legend for input section. Thinking bar removed (JSONL has no thinking token data). "Tool Calls" aggregate removed — each tool shown at same indentation level.
- `shorten_tool_name()` in formatter.py: MCP Tool-Namen kürzen (`mcp__plugin_xxx__tool` → `tool`)
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-t Keybinding: Tokens-Pane Content → Clipboard via pbcopy
- JSONL-Datenquelle: `message.usage.output_tokens` pro Content-Block (assistant Messages)
- Known limitation: output_tokens ~1.9x undercount (Claude Code Bug #27361), für Proportionen irrelevant
- **Token-Dedup (Session 11):** `extract_cache_turns()` groups consecutive assistant messages with identical `(cache_read, cache_creation, input_tokens)` into one API call entry. Uses MAX(output_tokens), aggregates unique content_blocks. Reduces 189 → 87 lines for test session.
- **% Removed (Session 11):** `_format_cache_call()` no longer calculates or displays cache-read percentage. Shows only raw JSONL values: CR, CC, D, output_tokens.
- **Thinking Display (Session 11):** Thinking content_blocks now include `output_tokens` from message-level usage. Rendered as `thinking (Xk out)` in expanded API call view.

**Session-Browser (Session 3):**
- `token_cumulative_n: Optional[int]` (monitor.py:48): steuert Modus. `None` = current session, `N` = letzte N Main-Sessions kumuliert
- Keyboard-Input in `run_tokens_loop()` (monitor.py:479-517): Ziffern → `token_input_buffer`, Enter → setzt `token_cumulative_n`, 'q' → setzt auf None, Backspace → löscht letzten Char
- `compute_cumulative_tokens(n)` (monitor.py:423-450): liest letzte N Main-Session-Files von Position 0 (kein Byte-Offset, full rescan), aggregiert Input/Output/Cache/Turns + per-tool output breakdown
- Input `0` → returns to current session view (`token_cumulative_n = None`)
- `format_token_profile_cumulative()` (formatter.py:324-371): rendert kumulative Ansicht mit granularem Output-Breakdown (per-tool + Text, same as current session view) + Per-Session-Breakdown (Input/Output/Turns pro File)
- Live-Prompt-Anzeige: `"Last N sessions › {buffer}_"` am Ende des Pane-Outputs

### Restart Hotkey (Kategorie: Display / UX)

`C-r` (Ctrl+R) keybinding in `configure_tmux_session()` (tmux_launcher.py): `respawn-pane -k` für alle 6 Panes across 4 Windows (0.0, 0.1, 1.0, 1.1, 2.0, 3.0) via `\;`-Chain. Restarts all monitor processes with their original commands.

**BUG (fixed, Session 6):** User reports "Monitor restarted" message appears but panes don't visibly restart.
- Root cause: `C-r` binding is global (`-T root`) with hardcoded session name via Python f-string (`f"{session_name}:0.0"`). When multiple monitor sessions exist simultaneously, the last `configure_tmux_session()` call wins → C-r respawns panes of the wrong session. User sees "Monitor restarted" display-message but no visual change because the respawn happens in a different (possibly hidden) session.
- Diagnosis: `tmux list-keys | grep C-r` showed binding targeting `monitor_cc_79b52c8d` while active session was `monitor_cc_f93afc17`. After killing all stale sessions and restarting fresh, C-r worked correctly.
- Fix: Replace `f"{session_name}"` with `"#{session_name}"` in bind-key call. tmux resolves `#{session_name}` at runtime to the session where the keypress occurs.

### Screen Clear Escape Sequence (Kategorie: Display / Robustheit)

`\033[2J\033[3J\033[H` an vier Stellen:
- `src/ui_mode.py`: in `sync_ui_to_screen()`
- `src/monitor.py`: in `run_rules_loop()`, `run_warnings_loop()`, and `run_tokens_loop()`

Bedeutung: `[2J` löscht sichtbaren Screen, `[3J` löscht Scrollback-Buffer, `[H` setzt Cursor auf Position 0,0.

### Hooks-Pane Display Fixes (Session 13)

Three fixes + one enhancement:

**Fix 1 — Full Content on Expand:**
`session-start-rules.sh` previously logged only summary strings ("injected: opus-xxx.md (108 lines)") to `hook_outputs.jsonl`. Expanded entries showed only metadata, not the rule file content.

Fix:
- `hook_logger.py`: `log_hook()` gains optional `content` parameter; if present, written as `content` field in JSONL entry. CLI: `sys.argv[6]` = content_file path.
- `session-start-rules.sh`: passes content_file path per opus file. `output` field retains summary for collapsed [+] view.
- `formatter.py` `build_hook_display_item()`: passes `content` field from entry into display item dict.
- `formatter.py` `format_hooks_block()` + `format_hooks_item_lines()`: expanded view uses `item['content']` if non-empty, falls back to `item['detail']`.

**Fix 2 — Remove Summary Hook:**
Removed redundant summary entry ("source=startup | injected N opus rules") from `session-start-rules.sh`. All 6 files shown individually.

**Fix 3 — Pre-SessionStart Entries:**
Historical entries from previous session appeared in hooks pane. Root cause: `_get_session_start_ts()` subtracted 60s buffer from first JSONL message timestamp.

Fix:
- Reduced buffer from 60s → 10s. SessionStart hooks fire within seconds of first message; 10s is safe margin.
- Added None fallback in `run_hooks_loop()` and `run_rules_loop()`: if `_get_session_start_ts()` returns None, `session_start_ts` is set to current UTC time.

**Enhancement — Per-File Opus Rule Injection:**
Previously one SessionStart hook assembled all 6 opus-*.md files into one 52.7KB `hookSpecificOutput.additionalContext` blob — exceeding Claude Code's 50K character limit (v2.1.89), causing truncation to 2KB preview.

Fix: Split into 7 separate SessionStart hooks in `settings.json`:
- 1x `session-start-rules.sh` (worktree logger only, no injection)
- 6x `session-start-rule-inject.sh` (one per opus-*.md file, each under 22KB)

Verified: Multiple SessionStart hooks each returning `additionalContext` produce separate `<system-reminder>` tags — they DO merge (contrary to GitHub source analysis which claimed "last one wins").

Verified: `_meta["anthropic/maxResultSizeChars"]` does NOT work for hook outputs (only MCP tool results).

### Hooks-Pane (Kategorie: Hook-Monitoring)

Eigenes tmux Pane (Window 1 "rules", Pane 1.1, rechts 50%) via `--mode hooks`:
- `run_hooks_loop()` in monitor.py: pollt `process_hook_log_for_display()`
- `format_hook_event()` in formatter.py: `[timestamp] hook_event | hook_script` + output
- Scrolling stream (kein Screen-clear) — jeder Hook mit Output wird sofort angezeigt
- Hooks ohne Output werden gefiltert (`if not output: continue`)
- M-h Keybinding: Hooks-Pane Content → Clipboard via pbcopy
- Hook-Routing geändert: `process_hook_log()` nur noch für InstructionsLoaded → Rules-Pane. Kein Buffering mehr (`pending_pretooluse_hooks`, `pending_user_prompt_hook` entfernt).

### Warnings-Pane (Kategorie: Format-Stabilität)

Eigenes tmux Pane (Window 3 "debug", Pane 3.0, fullscreen) via `--mode warnings`:
- `run_warnings_loop()` in monitor.py: pollt `monitor_sessions()`, rendert `format_warnings_block()`
- `format_unknown_type_warning()` in formatter.py (formatter.py:229-230): `[!] Unknown JSONL type: <type> (seen Nx)`
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-w Keybinding: Warnings-Pane Content → Clipboard via pbcopy (tmux_launcher.py:132, Pane 3.0)

### Workers-Pane (Kategorie: Worker-Monitoring, Session 3+7+9+10)

Eigenes tmux Pane (Window 2 "workers", Pane 2.0, links 50%) via `--mode workers`. Rendert nur Workers (Subagents haben jetzt ein eigenes Pane):
- `run_workers_loop()` in monitor.py: pollt `list_workers()`, rendert `format_workers_block()`. Keyboard-Input (Digits 1-9 toggle) + SGR Mouse-Click toggle + Scroll.
- `list_workers(project_path)` (monitor.py): scannt tmux-Sessions mit Prefix `worker-{project_name}-`, liest Status + Env-Variablen pro Worker
- `detect_worker_status(session)` (monitor.py): prüft `#{pane_dead}` für exited-Status; analysiert `#{window_activity}` Timestamp für idle-Detection (10s Threshold)
- `get_tmux_env(session, var)` (monitor.py): liest WORKER_SPAWNED, WORKER_PURPOSE aus tmux show-environment
- `get_worker_project_name(project_path)` (monitor.py): extrahiert Projektname worktree-aware (splittet bei `/.claude/worktrees/`)
- `find_worker_jsonl(session_name)` (monitor.py): Worker JSONL Discovery via `pane_current_path` → `encode_project_path()` → `~/.claude/projects/<encoded>/`. Worktree-aware: direkter Lookup auf Worktree-Verzeichnis (kein Fallback auf Base-Projekt).
- `format_workers_block(workers, expand_states, worker_turns, line_map, hover_row, scroll_offsets)` (formatter.py): Expand/Collapse per Worker. Collapsed: `[+] [idx] name STATUS spawn_time` + truncated purpose. Expanded: `[-] [idx] name STATUS spawn_time` + full purpose + scrollable Cache-Tracker Token-View (CR/CC/D per API call via `format_cache_tracker()`). Hover-Highlight: `HOVER_BG` on header line when `hover_row` matches.
- State: `worker_expand_states: Dict[str, bool]`, `worker_scroll_offsets: Dict[str, int]`, `worker_line_map: Dict[int, str]`, `hover_row: Optional[int]` (monitor.py)
- Status-Farben: working=GREEN, idle=YELLOW, exited=RED, unknown=WHITE
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-k Keybinding: Workers-Pane Content → Clipboard via pbcopy (tmux_launcher.py, Pane 2.0)
- Dual poll intervals: Input polling at 50ms (`INPUT_POLL_INTERVAL`), data refresh at 500ms (`POLL_INTERVAL`).
- **Mouse UX:** Mode 1003 (Any Event Tracking) + SGR 1006. Input-Buffer Draining (while-loop). Hover-Highlight. Scroll (button 64/65 → increment/decrement scroll_offset). All reads via `os.read(fd, 1)` (unbuffered).
- Verifiziert gegen tmux Source Code (`repo/input-keys.c:755-822`): tmux forwarded SGR Mouse Events an App wenn `MODE_MOUSE_ALL` + `MODE_MOUSE_SGR` gesetzt sind. Kein Konflikt mit tmux `mouse on`.

### Subagents-Pane (Window 2, Pane 2.1, Session 10)

Eigenes tmux Pane (Window 2 "workers", Pane 2.1, rechts 50%) via `--mode subagents`. Split aus Workers-Pane (vorher kombiniert in Pane 2.0).
- `run_subagents_loop()` in monitor.py: pollt `monitor_sessions()` + per-Agent JSONL, rendert `render_subagents_with_tokens()`. Keyboard (Digits 1-9) + SGR Mouse (click, scroll, hover).
- `load_historical_subagents()` in monitor.py: setzt neueste Main-Session + deren Agent-Files (`filepath.parent/filepath.stem/subagents/agent-*.jsonl`) auf Position 0 — nur aktuelle Session, nicht alle historischen.
- `find_agent_jsonl(agent_id)` in monitor.py: sucht `agent-{id}.jsonl` in aktiven Sessions via `find_active_sessions()`.
- `render_subagents_with_tokens(metadata, turns_by_agent, ...)` in monitor.py: collapsible Agent-Liste. Collapsed: `[+/-] [idx] name (id) - timestamp`. Expanded: per-Agent Cache-Tracker Token-View via `format_cache_tracker()` mit separatem `agent_cache_scroll_offsets` Dict.
- `toggle_subagent_state(agent_id)` in subagent_ui.py: toggled `subagent_states[agent_id]`; nutzt `.get()` Default sodass neue Agents direkt togglebar sind ohne Pre-Initialisierung.
- State: `agent_turns`, `agent_pane_line_map`, `agent_pane_hover_row`, `agent_cache_scroll_offsets` (monitor.py); `subagent_states` (subagent_ui.py)
- `ui_mode_active = True` gesetzt beim Start so `handle_subagent_call()` Metadata via `track_subagent_metadata()` populiert statt inline display.
- **Session-Reset (Session 11):** `run_subagents_loop()` detects main session JSONL change via `_get_newest_main_session()`. On change: clears `subagent_metadata`, `agent_turns`, expand/scroll states, `subagent_states`, `file_positions`, `tool_use_caches`; re-runs `load_historical_subagents()`. Prevents cross-session accumulation of stale agents.
- **Scroll Fix (Session 11):** `_find_agent_at_row(row, line_map)` walks upward from mouse row to find parent agent ID. Scroll events (button 64/65) now use this instead of direct `agent_pane_line_map.get(row)`, fixing scroll in expanded cache-tracker areas where row maps to None.

### Main Pane Session-Reset (Session 11)

`run_streaming_loop()` tracks `current_main_session` via `_get_newest_main_session()`. Each poll cycle checks if newest main JSONL changed. On change: resets `file_positions[newest] = 0`, clears screen (`\033[2J\033[3J\033[H`), prints `--- New session detected ---` separator. Replays new session from beginning, old session messages not repeated.

### print_session_status Fix (Kategorie: Display / Startup)

`print_session_status()` und `print_startup_message()` werden nur für streaming/UI modes aufgerufen, nicht für dedizierte Panes (rules, warnings, hooks). Fix in `workflow.py` und `monitor.py`.

### Farb-Palette (Kategorie: Architektur — RESOLVED)

Alle Farb-Konstanten zentral in `src/constants.py` definiert (256-color ANSI). Alle Module importieren von dort. Keine Duplikation, keine Konflikte. Siehe Rule: `.claude/rules/tui-standards.md`.

### Logging im Display (Kategorie: Observability)

`format_usage()` und `format_turn_total()` wurden entfernt. `PASTEL_YELLOW` und `SIGNAL_PINK` Farbkonstanten wurden ebenfalls entfernt.

**Stand nach Session 3 (Logging-Entfernung):**

`src/formatter.py`: **0** `log_tagged()`-Aufrufe. Kein `long_output_logger` mehr — `LONG_OUTPUT_THRESHOLD`-Check (formatter.py:107-119) nutzt nur noch `LIGHT_RED_BG` Farb-Highlight, kein File-Logging mehr.

`src/ui_mode.py`: **0** `log_tagged()`-Aufrufe. Alle 4 ehemaligen Calls (`08_ui_rendering.log`) wurden entfernt. Kein `import logging` im Modul.

`src/subagent_ui.py`: **0** `log_tagged()`-Aufrufe. Alle 5 ehemaligen Calls (`08_ui_rendering.log`) wurden entfernt.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

### Screenshot-Tool (Kategorie: Dev Tooling / Feedback)

`dev/display/screenshot_panes.py`: Captures all 6 tmux panes across 4 windows via `tmux capture-pane -p -e`, renders each to PNG via `termshot --raw-read`, combines with Pillow into single layout image → `/tmp/monitor_cc_screenshot.png`.

Dependencies: `termshot` (brew), `Pillow` (pip). Auto-detects running `monitor_cc_*` session.

Purpose: Claude reads the PNG per Read-Tool for visual layout verification during development.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- Rules-Pane: `active_rules` ist ein Set (nur add, kein remove) — Rules verschwinden nicht wenn sie out-of-scope gehen [RESOLVED Session 12: `load_historical_rules()` clears both sets on session change]
- InstructionsLoaded Hook feuert nicht nach /clear oder /compact (#30973, #31017) — Monitor kann Reloads nicht tracken
- Session-JSONL enthält keine Rules/Instructions-Daten (verifiziert via dev/display/jsonl_exploration Scripts)

## Quellen

- GitHub anthropics/claude-code #19377 — YAML array syntax for `paths:` broken (CSV parser bug)
- GitHub anthropics/claude-code #33581 — Multiple `paths:` entries silently fail (same root cause)
- GitHub anthropics/claude-code #30973 — InstructionsLoaded missing after compaction
- GitHub anthropics/claude-code #31017 — InstructionsLoaded missing on /clear
- GitHub anthropics/claude-code #16299 — Path-scoped rules load globally (opposite bug, version-dependent)
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
