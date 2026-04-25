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
**BUG-CLASS (fixed, 2026-04-25 Performance Session):** All 9 stdin-driven panes were polling at a 50ms floor via `time.sleep(INPUT_POLL_INTERVAL)` at the end of each loop iteration → input latency 0–50ms (~25ms median) for hover/click/scroll/keyboard regardless of how fast the rest of the loop ran. Replaced with `wait_for_input(INPUT_POLL_INTERVAL)` from `src/input/click_handler.py` — a `select.select([_stdin_fd], [], [], timeout)` wrapper with `time.sleep` fallback when stdin not in raw mode. Loop wakes immediately on any byte arriving on stdin (mouse event, keypress) OR after the timeout expires. Smoke test 11.9ms wake-latency on stdin-mid-wait. Affected modules: `panes/{token,rules,warnings,waste}_pane.py`, `hooks/hooks_pane.py`, `workers/worker_pane.py` (two call sites: try body + except handler), `proxy_display/{pane,worker_proxy_pane}.py`. `metadata_pane.py` unchanged — has no stdin handler. Pattern A (direct sleep replacement) chosen over Pattern B (refresh-aligned timeout) because `warnings_pane`'s `WARNINGS_POLL_INTERVAL=10s` would otherwise mean up to 10s blocking on input — Pattern B would have made warnings unresponsive.

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
- **Token-Dedup (Session 11, updated Session 17):** `extract_cache_turns()` deduplicates streaming chunks using `requestId` as primary key (falls back to `(cache_read, cache_creation, input_tokens)` for entries without requestId). Uses MAX(output_tokens), aggregates unique content_blocks. `request_id` stored as persistent field on api_call dicts for incremental merge in `build_cache_turns()`.
- **% Removed (Session 11):** `_format_cache_call()` no longer calculates or displays cache-read percentage. Shows only raw JSONL values: CR, CC, D, output_tokens.
- **Thinking Display (Session 11):** Thinking content_blocks now include `output_tokens` from message-level usage. Rendered as `thinking (Xk out)` in expanded API call view.

### Proxy Pane Redesign (Session 17, 2026-04-09)

**Turn-based expand/collapse:** Proxy Pane redesigned from per-request expand to two-level turn-based hierarchy. Turn header is clickable (expand/collapse). Expanded turn shows: request metadata lines (compact, also clickable) + message lines. Request expand shows messages belonging to that specific request.

**REQ numbering sync:** `opus_req_num` reset at each turn boundary using cumulative `api_calls` count from session JSONL turns. Eliminates cross-turn drift from proxy-only requests (that don't appear in session JSONL). Helper requests (non-haiku, BP:0) get sub-numbers (#7.1, #7.2).

**Modified message detection:** When consecutive requests have same message_count but different total chars, backwards scan from end finds divergence point. `content_tail` field (last 500 chars) stored in `_extract_raw_payload_fields()` enables showing the actual new content appended to modified messages.

**Turn header config:** Shows `effort:X`, `think:Yk(type)` from API payload's `output_config.effort` and `thinking.budget_tokens`/`thinking.type`. Red highlight when values change between turns.

**Image grouping (Main Pane):** `format_user_media()` in formatter.py now accepts list of media items grouped by timestamp. Multiple images rendered as single line: `[4x IMAGE: image/png]`.

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
Previously one SessionStart hook assembled all 6 opus-*.md files into one 52.7KB `hookSpecificOutput.additionalContext` blob — exceeding Claude Code's per-hook additionalContext limit, causing truncation to 2KB preview. Live-tested limit (Session 14): ~10KB per hook (9,945 bytes passed, 10,081 bytes truncated). GitHub CHANGELOG v2.1.89 claims 50K — this is incorrect or refers to a different limit.

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
- **Universal-logger-Filter (hooks-redesign branch):** `_is_noise_entry()` in monitor.py filtert Einträge mit `hook_script.endswith('universal-logger.sh')` AND `output.startswith('tool=')` heraus — in `load_historical_hooks()` und `process_hook_log_for_display()`.
- **Persisted additionalContext Loading (hooks-redesign branch):** `_scan_persisted_hook_files()` scannt `tool-results/hook-*-additionalContext.txt` in aktiven Sessions. `_enrich_with_persisted()` matched Dateien zu Hook-Items via Timestamp-Nähe (< 60s). Wenn Match: `item['content']` = Dateiinhalt, `item['was_truncated'] = True`.
- **Truncation-Threshold (hooks-redesign branch):** `format_hooks_block()` zeigt Warning wenn `len(content) > 10_000` (vorher 50_000). Passt zum live-getesteten Limit von ~10KB (Session 14).

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

**BUG (fixed, 2026-04-05 hooks-content branch):** Hooks-Pane expand shows only green summary line — expanded content not visible.

Root cause: Viewport-Bug. Die 6 `SessionStart`-Entries mit injected-Content (opus-communication.md etc.) stehen am Anfang von `hooks_display_items` (erste Items, älteste Timestamps). Beim Expand werden ihre Content-Lines in `all_lines` direkt nach dem Header eingefügt — aber da der Display bottom-anchored ist, springt der Viewport nach unten um genau M Lines (M = Anzahl Content-Lines). Header UND Content landen dadurch ÜBER dem neuen Viewport. Nur der Sticky-Header zeigte den Item-Header.

Fix:
- `format_hooks_block()` in `formatter.py`: neuer optionaler `item_positions_out: Optional[dict]` Parameter. Wenn übergeben, wird `{item_idx: all_lines_line_idx}` für jeden Item befüllt.
- `run_hooks_loop()` in `monitor.py`: nach Expand via Click wird `just_expanded_idx` gesetzt. Nach dem ersten `format_hooks_block()`-Aufruf: wenn `item_positions[just_expanded_idx]` UNTER dem Viewport-Start liegt (`item_line < start`), wird `hooks_scroll_offset` so gesetzt dass der Item-Header oben im Viewport erscheint (`max(0, total_lines - viewport_lines - item_line)`). Danach zweiter `format_hooks_block()`-Aufruf mit dem korrigierten Offset.

Deliverable 2 (Truncation Warning): Wenn Content > 50K Zeichen, zeigt `format_hooks_block()` eine Warning-Line direkt nach dem Header: `[content N chars — exceeds 50K limit, Claude Code may have persisted additionalContext to disk]`. Note: Der 50K-Threshold im Code ist zu hoch — live-getestetes Limit ist ~10KB per hook (Session 14). Threshold sollte auf 10K angepasst werden. Alle 9 aktuellen Entries liegen unter 9.5KB (nach Split von communication in 2, workers in 3 Teile).

### Buddy/Teammate Notifications (buddy-notify branch, 2026-04-05)

**D1 — hook_events in hook_outputs.jsonl (vollständig):**

| hook_event | count |
|---|---|
| ConfigChange | 188 |
| CwdChanged | 1 |
| InstructionsLoaded | 5692 |
| Notification | 73 |
| PermissionRequest | 25 |
| PostToolUse | 1395 |
| PostToolUseFailure | 57 |
| PreToolUse | 7908 |
| SessionEnd | 2 |
| SessionStart | 64 |
| Stop | 233 |
| SubagentStart | 33 |
| SubagentStop | 32 |
| UserPromptSubmit | 12568 |

**Buddy-relevante Events:** Keines vorhanden.
- `TeammateIdle` ist in `constants.py` als `HOOK_TEAMMATE_IDLE = 'TeammateIdle'` definiert und in `HOOK_EVENT_CATEGORIES` als `'agent'`-Kategorie (BLUE) eingetragen — aber **nie in `hook_outputs.jsonl` gefeuert** (0 Occurrences).
- `Notification`-Events (73 total): nur `type=idle_prompt` und `type=permission_prompt` — beide nicht buddy-relevant.

**D2 — Designentscheidung (für wenn TeammateIdle auftritt):**

TeammateIdle-Events würden automatisch via bestehenden Hooks-Pane (`run_hooks_loop()` → `build_hook_display_item()` → `format_hooks_block()`) angezeigt werden, da die Kategorie bereits als `'agent'` → BLUE konfiguriert ist.

Für die Workers-Pane-Integration (Window 2) wäre nötig:
- `process_hook_log_for_display()` erweitern um buddy events zu sammeln
- Neuer `buddy_events: list` state in `run_workers_loop()`
- Buddy-Section am Ende von `format_workers_block()`: `[timestamp] TeammateIdle — <buddy_name>` in BLUE, analog zu Worker-Header-Format
- Filter: nur Events >= `session_start_ts` (gleicher Mechanismus wie Hooks-Pane)

**Status: D3-D5 SKIPPED** — keine buddy events in `hook_outputs.jsonl`. Implementation deferred bis TeammateIdle tatsächlich feuert.

## Quellen

- GitHub anthropics/claude-code #19377 — YAML array syntax for `paths:` broken (CSV parser bug)
- GitHub anthropics/claude-code #33581 — Multiple `paths:` entries silently fail (same root cause)
- GitHub anthropics/claude-code #30973 — InstructionsLoaded missing after compaction
- GitHub anthropics/claude-code #31017 — InstructionsLoaded missing on /clear
- GitHub anthropics/claude-code #16299 — Path-scoped rules load globally (opposite bug, version-dependent)
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
- GitHub anthropics/claude-code CHANGELOG v2.1.89: hook output > 50K → persisted-output (file path + preview statt direkter Injection). KORREKTUR: Live-Test (Session 14) zeigt ~10KB per-hook limit, nicht 50K.
- GitHub anthropics/claude-code #41799: Hooks docs omit >50K output file-path preview behavior
- Live-Test Session 14 (2026-04-05): additionalContext per-hook limit = ~10KB (9,945 bytes ✅, 10,081 bytes ❌). Binäre Suche über 4 Iterationen. Multiple hooks merge as separate system-reminders.

## Rules Architecture: Hook-based Injection with Target Control (Session 15, 2026-04-05)

### Old Approach (Static .claude/rules/)

**Problem:** All rules in `Monitor_CC/.claude/rules/` loaded statically for ALL sessions — both Opus and Workers. No target-group control. Rules with `paths: .claude/worktrees/**` frontmatter (scalar string, not array) were likely silently dropped (see GitHub #19377, #33581 — YAML array syntax required for `paths:`). In practice, every rule loaded for every session.

**Files:** `Monitor_CC/.claude/rules/` contained:
- 7 symlinks → `~/.claude/shared-rules/global/` (code-standards, code-organization, decisions, dev-convention, documentation, project-standards, claude-md-convention)
- 3 local files with `paths: .claude/worktrees/**` (dev-verification.md, monitor-standards.md, tui-standards.md)
- Note: hook-limits.md lived in `~/.claude/shared-rules/monitor/` root, injected by existing opus hook pointing to that root

### New Approach (Hook-based Injection with Target Control)

**Architecture:** 6 SessionStart hooks inject rules based on CWD at session start. Target groups enforced by hook scripts.

**Directory structure:**
```
~/.claude/shared-rules/monitor/
├── opus/
│   └── hook-limits.md              — Opus only (hook design constraints)
├── worker1/
│   └── dev-verification.md         — Workers only (bug fix/feature verification workflow)
├── worker2/
│   ├── monitor-standards.md        — Workers only (Monitor_CC coding standards)
│   └── tui-standards.md            — Workers only (TUI reference patterns)
├── shared-a/
│   └── documentation.md            → symlink to global (6,817 bytes)
├── shared-b/
│   ├── code-organization.md        → symlink to global
│   ├── decisions.md                → symlink to global
│   └── dev-convention.md           → symlink to global  (9,065 bytes total)
└── shared-c/
    ├── claude-md-convention.md     → symlink to global
    ├── code-standards.md           → symlink to global
    └── project-standards.md       → symlink to global  (3,678 bytes total)
```

**Hook scripts:**
- `session-start-project-rules.sh` (existing) — Opus-only: injects RULE_DIR for PROJECT_FILTER, excludes worktrees
- `session-start-monitor-worker.sh` (new) — Worker-only: injects RULE_DIR only when CWD contains `/.claude/worktrees/`, project-filtered
- `session-start-monitor-shared.sh` (new) — Shared: injects RULE_DIR for all sessions matching PROJECT_FILTER (no worktree exclusion)

**6 SessionStart hooks in `~/.claude/settings.json`:**
1. `RULE_DIR=monitor/opus PROJECT_FILTER=Monitor_CC session-start-project-rules.sh` → Opus only
2. `RULE_DIR=monitor/worker1 PROJECT_FILTER=Monitor_CC session-start-monitor-worker.sh` → Workers only
3. `RULE_DIR=monitor/worker2 PROJECT_FILTER=Monitor_CC session-start-monitor-worker.sh` → Workers only
4. `RULE_DIR=monitor/shared-a PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → Both
5. `RULE_DIR=monitor/shared-b PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → Both
6. `RULE_DIR=monitor/shared-c PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → Both

**Size constraint:** Each hook injects ≤9,500 bytes (10KB per-hook limit, safety margin). Split into subdirectories to respect this: worker1+worker2 for worker rules (5,124 + 6,505 bytes), shared-a/b/c for global rules (6,817 + 9,065 + 3,678 bytes).

**Monitor_CC/.claude/rules/:** Now empty. All rules delivered via hook injection.

## Session 18 (2026-04-15) — Display Drift Update

Earlier IST sections reference the pre-Session-17 layout (4 windows, 6 panes) and pre-reversal scroll direction. This section documents the current prod state. Where an earlier section conflicts, THIS section is authoritative.

### Current tmux Layout (src/tmux_launcher.py:45-66, 131-137)

5 windows, 10 panes. Source of truth: `configure_tmux_session()` `pane_titles` dict.

| Window | Name | Panes |
|---|---|---|
| 0 | main | 0.0 MAIN (70%), 0.1 TOKENS (30%) |
| 1 | proxy | 1.0 PROXY (70%), 1.1 METADATA (30%) |
| 2 | rules | 2.0 RULES (50%), 2.1 HOOKS (50%) |
| 3 | workers | 3.0 WORKERS (34%), 3.1 WORKER-PROXY (33%), 3.2 WORKER-METADATA (33%) |
| 4 | debug | 4.0 WARNINGS (fullscreen) |

Cross-reference: all earlier IST entries that say e.g. `Window 1 "rules" Pane 1.0` now mean `Window 2 Pane 2.0`. The functional description of each pane is still correct, only the window index shifted.

New panes added since the last IST pass: Proxy Pane (Window 1.0), Metadata Pane (Window 1.1), Worker-Proxy Pane (Window 3.1), Worker-Metadata Pane (Window 3.2).

### Scroll Direction Reversed (traditional)

Wheel up = viewport moves toward earlier content (up), wheel down = viewport moves toward later content (down). Applied in ALL interactive panes: token, warnings, workers, hooks, metadata, proxy, worker-proxy. Reverses the Session-10..16 behaviour where wheel up scrolled toward newer content.

Implementation: each pane's mouse handler maps button 64 → `scroll_offset += N`, button 65 → `scroll_offset -= N` (or equivalent semantic).

### ANSI Header Overdraw Pattern (Pane Header Contract)

Bug: when the body print overflows the pane height (terminal line wrap), the rendered top line of the body replaces the sticky header written by the pane loop itself. tmux `pane-border-status` still shows, but any app-level header line drawn on row 1 is lost.

Fix: after body print, overdraw the header using `\033[H{header}\033[K` (cursor home + header text + erase-to-EOL). Header always survives body overflow.

Applied: `src/warnings_pane.py`, `src/proxy_display/pane.py` (function `run_worker_proxy_loop`). Pattern is generalizable — any pane that draws its own header on row 1 should use it.

### Warnings Pane — 10s Polling + `r` Key

- Poll interval: 10s (was 0.5s). Warnings are rare and don't need sub-second latency; 0.5s burned CPU for no gain.
- Manual refresh: `r` key triggers immediate poll outside the 10s cycle.
- Header: `WARNINGS  [r]efresh · last: HH:MM:SS · polling: 10s`
- Source: `src/warnings_pane.py`

### Worker-Proxy Pane — Digit Switch Header

- Shows the proxy log of ONE selected worker at a time.
- Header: `WORKER-PROXY [1*]selected [2]other [3]another` — active selection marked with `*`.
- Digit keys 1-9 switch selection. IPC via `write_selection()` exposed from `src/workers/__init__.py`.
- Source: `src/proxy_display/pane.py` (function `run_worker_proxy_loop`)
- State clear rule: `worker_proxy_entries` (and all associated state) is cleared when `_worker_proxy_workers` is empty OR `current_worker` from selection file is not in worker list OR `worker_name != last_worker_name`. Ensures stale entries don't persist when all workers exit.
- Thinking block display: Thinking blocks render as `[N] thinking      text:Xc sig:Yc` to expose signature byte length (encrypted thinking carrier, ~400 chars typical on Opus 4.7 `display: summarized`). Field `sig_chars` added to block dict in `src/proxy/message_summary.py`. `chars` field remains `len(thinking_text)` only — signature NOT counted (signatures are not billed as input tokens per Anthropic docs).

### Mouse Wheel Scroll Contract (all interactive panes)

Button codes (post-reversal):
- `64` (wheel up)   → `scroll_offset += N`   (viewport up, older content)
- `65` (wheel down) → `scroll_offset -= N`   (viewport down, newer content)
- `scroll_offset` clamped to `[0, max_scroll]`

N is typically 1 or 3 depending on pane density. See `src/token_pane.py` as canonical reference pattern.

