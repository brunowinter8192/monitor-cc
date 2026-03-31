# Pipe Section: Display

## Status Quo

- `formatter.py`: 21 Funktionen + Workers-Block + Session-Browser, color-coded output (green=main, blue=subagent, red=error, pastel=meta)
- `ui_mode.py`: `format_rules_block()` rendert `ACTIVE RULES (XP / YG)` mit `[P]`/`[G]` Prefix pro Regel, pastel blue
- `subagent_ui.py`: collapsible list, Digits 1-9 toggle via `click_handler.py`
- `ui_mode.py`: `run_ui_mode()` Screen-clear refresh loop mit raw stdin
- Workers-Pane (Window 2, Pane 2.0): `run_workers_loop()` + `format_workers_block()` — zeigt Worker-Name, Status, Spawn-Zeit, Purpose

**BUG (fixed):** `active_rules` was populated by `process_hook_log()` but never rendered in streaming mode.
Fix: `run_rules_loop()` in monitor.py + dedicated `--mode rules` tmux pane (Window 1, Pane 1.0).
**BUG (fixed):** Project `.claude/rules/*.md` did not appear — root cause was YAML array syntax in `paths:` frontmatter (Claude Code Bug #19377/#33581). CSV parser expects string, receives JS Array from `yaml.parse()`, producing broken globs. Fix: CSV string format (`paths: src/**, workflow.py`). All project rules now load correctly via InstructionsLoaded hook.
**BUG (fixed):** Rules-Pane showed historical rules from previous sessions because `hook_log_position` was set to 0 (read from beginning of hook log). Fix: removed `hook_log_position = 0` override, now starts from EOF like all other modes.

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

**Session-Browser (Session 3):**
- `token_cumulative_n: Optional[int]` (monitor.py:48): steuert Modus. `None` = current session, `N` = letzte N Main-Sessions kumuliert
- Keyboard-Input in `run_tokens_loop()` (monitor.py:479-517): Ziffern → `token_input_buffer`, Enter → setzt `token_cumulative_n`, 'q' → setzt auf None, Backspace → löscht letzten Char
- `compute_cumulative_tokens(n)` (monitor.py:423-450): liest letzte N Main-Session-Files von Position 0 (kein Byte-Offset, full rescan), aggregiert Input/Output/Cache/Turns + per-tool output breakdown
- Input `0` → returns to current session view (`token_cumulative_n = None`)
- `format_token_profile_cumulative()` (formatter.py:324-371): rendert kumulative Ansicht mit granularem Output-Breakdown (per-tool + Text, same as current session view) + Per-Session-Breakdown (Input/Output/Turns pro File)
- Live-Prompt-Anzeige: `"Last N sessions › {buffer}_"` am Ende des Pane-Outputs

### Restart Hotkey (Kategorie: Display / UX)

`C-r` (Ctrl+R) keybinding in `configure_tmux_session()` (tmux_launcher.py:142-150): `respawn-pane -k` für alle 7 Panes across 4 Windows (0.0, 0.1, 1.0, 1.1, 2.0, 3.0, 3.1) via `\;`-Chain. Restarts all monitor processes with their original commands.

**BUG (fixed, Session 6):** User reports "Monitor restarted" message appears but panes don't visibly restart.
- Root cause: `C-r` binding is global (`-T root`) with hardcoded session name via Python f-string (`f"{session_name}:0.0"`). When multiple monitor sessions exist simultaneously, the last `configure_tmux_session()` call wins → C-r respawns panes of the wrong session. User sees "Monitor restarted" display-message but no visual change because the respawn happens in a different (possibly hidden) session.
- Diagnosis: `tmux list-keys | grep C-r` showed binding targeting `monitor_cc_79b52c8d` while active session was `monitor_cc_f93afc17`. After killing all stale sessions and restarting fresh, C-r worked correctly.
- Fix: Replace `f"{session_name}"` with `"#{session_name}"` in bind-key call. tmux resolves `#{session_name}` at runtime to the session where the keypress occurs.

### Screen Clear Escape Sequence (Kategorie: Display / Robustheit)

`\033[2J\033[3J\033[H` an vier Stellen:
- `src/ui_mode.py`: in `sync_ui_to_screen()`
- `src/monitor.py`: in `run_rules_loop()`, `run_warnings_loop()`, and `run_tokens_loop()`

Bedeutung: `[2J` löscht sichtbaren Screen, `[3J` löscht Scrollback-Buffer, `[H` setzt Cursor auf Position 0,0.

### Hooks-Pane (Kategorie: Hook-Monitoring)

Eigenes tmux Pane (Window 1 "rules", Pane 1.1, rechts 50%) via `--mode hooks`:
- `run_hooks_loop()` in monitor.py: pollt `process_hook_log_for_display()`
- `format_hook_event()` in formatter.py: `[timestamp] hook_event | hook_script` + output
- Scrolling stream (kein Screen-clear) — jeder Hook mit Output wird sofort angezeigt
- Hooks ohne Output werden gefiltert (`if not output: continue`)
- M-h Keybinding: Hooks-Pane Content → Clipboard via pbcopy
- Hook-Routing geändert: `process_hook_log()` nur noch für InstructionsLoaded → Rules-Pane. Kein Buffering mehr (`pending_pretooluse_hooks`, `pending_user_prompt_hook` entfernt).

### Warnings-Pane (Kategorie: Format-Stabilität)

Eigenes tmux Pane (Window 3 "debug", Pane 3.0, links 50%) via `--mode warnings`:
- `run_warnings_loop()` in monitor.py: pollt `monitor_sessions()`, rendert `format_warnings_block()`
- `format_unknown_type_warning()` in formatter.py (formatter.py:229-230): `[!] Unknown JSONL type: <type> (seen Nx)`
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-w Keybinding: Warnings-Pane Content → Clipboard via pbcopy (tmux_launcher.py:132, Pane 3.0)

### Workers-Pane (Kategorie: Worker-Monitoring, Session 3+7)

Eigenes tmux Pane (Window 2 "workers", Pane 2.0, fullscreen) via `--mode workers`:
- `run_workers_loop()` in monitor.py: pollt `list_workers()`, rendert `format_workers_block()` bei Änderungen. Keyboard-Input (Digits 1-9 toggle) + SGR Mouse-Click toggle via `read_keypress()` + `read_mouse_event()`
- `list_workers(project_path)` (monitor.py): scannt tmux-Sessions mit Prefix `worker-{project_name}-`, liest Status + Env-Variablen pro Worker
- `detect_worker_status(session)` (monitor.py): prüft `#{pane_dead}` für exited-Status; analysiert `#{window_activity}` Timestamp für idle-Detection (10s Threshold)
- `get_tmux_env(session, var)` (monitor.py): liest WORKER_SPAWNED, WORKER_PURPOSE aus tmux show-environment
- `get_worker_project_name(project_path)` (monitor.py): extrahiert Projektname worktree-aware (splittet bei `/.claude/worktrees/`)
- `find_worker_jsonl(session_name)` (monitor.py): Worker JSONL Discovery via `pane_current_path` → `encode_project_path()` → `~/.claude/projects/<encoded>/`
- `extract_worker_tool_calls(jsonl_path)` (monitor.py): Parsed Worker-JSONL für tool_use Entries (tool name, input, timestamp, call_number)
- `format_workers_block(workers, expand_states, tool_calls_by_worker, line_map)` (formatter.py): Expand/Collapse per Worker. Collapsed: `[+] [idx] name STATUS spawn_time` + truncated purpose. Expanded: `[-] [idx] name STATUS spawn_time` + full purpose + tool call list (tool name + input preview, kein Output)
- State: `worker_expand_states: Dict[str, bool]`, `worker_line_map: Dict[int, str]` (monitor.py)
- Status-Farben: working=GREEN, idle=YELLOW, exited=RED, unknown=WHITE
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-k Keybinding: Workers-Pane Content → Clipboard via pbcopy (tmux_launcher.py:131, Pane 2.0)
- **Known UX issue (Session 7):** Mouse-Click Response langsam und inkonsistent. Ursache: Mode 1000 (nur Clicks) + Single-Read pro 0.5s Poll-Iteration. Geplant: Mode 1003 (Motion Tracking), Hover-Highlight, Input-Buffer Draining.

### Subagent-Pane Mouse Support (Kategorie: Display / UX, Session 7)

SGR Mouse-Click Support in Subagent-Pane (Window 3, Pane 3.1):
- `enable_mouse()` / `disable_mouse()` in click_handler.py: `\033[?1000h\033[?1006h` / `\033[?1000l\033[?1006l`
- `read_mouse_event(first_char)` in click_handler.py: Parsed SGR sequence `\033[<b;col;rowM/m`, returns `(button, col, row)` für press, None für release/failure. Non-blocking via `select.select` mit 0.05s Timeout.
- `handle_pending_keypresses()` in ui_mode.py: `\033` → Mouse-Branch (lookup row in `line_to_agent_map`), sonst → Digit-Branch (1-9 toggle)
- `line_to_agent_map` (subagent_ui.py): bereits seit Session 3 vorhanden, mapped Display-Zeile → Agent-ID
- Keyboard Digits 1-9 weiterhin funktional als Fallback
- Verifiziert gegen tmux Source Code (`repo/input-keys.c:755-822`): tmux forwarded SGR Mouse Events an App wenn `MODE_MOUSE_STANDARD` + `MODE_MOUSE_SGR` gesetzt sind. Kein Konflikt mit tmux `mouse on`.
- **Known UX issue:** Gleich wie Workers-Pane — langsame Response, kein Hover-Feedback.

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

`dev/display/screenshot_panes.py`: Captures all 7 tmux panes across 4 windows via `tmux capture-pane -p -e`, renders each to PNG via `termshot --raw-read`, combines with Pillow into single layout image → `/tmp/monitor_cc_screenshot.png`.

Dependencies: `termshot` (brew), `Pillow` (pip). Auto-detects running `monitor_cc_*` session.

Purpose: Claude reads the PNG per Read-Tool for visual layout verification during development.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- Rules-Pane: `active_rules` ist ein Set (nur add, kein remove) — Rules verschwinden nicht wenn sie out-of-scope gehen
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
