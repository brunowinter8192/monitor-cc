# Pipe Section: Display

## Status Quo (IST)

- `formatter.py`: color-coded output (green=main, red=error, pastel=meta)
- Workers-Pane (Window 2, Pane 2.0): `run_workers_loop()` + `format_workers_block()` — zeigt Worker-Name, Status, Spawn-Zeit, Purpose. Three-pane split: Workers (2.0) | Worker-Proxy (2.1) | Worker-Metadata (2.2).
**BUG-CLASS (fixed, 2026-04-25 Performance Session):** All 9 stdin-driven panes were polling at a 50ms floor via `time.sleep(INPUT_POLL_INTERVAL)` at the end of each loop iteration → input latency 0–50ms (~25ms median) for hover/click/scroll/keyboard regardless of how fast the rest of the loop ran. Replaced with `wait_for_input(INPUT_POLL_INTERVAL)` from `src/input/click_handler.py` — a `select.select([_stdin_fd], [], [], timeout)` wrapper with `time.sleep` fallback when stdin not in raw mode. Loop wakes immediately on any byte arriving on stdin (mouse event, keypress) OR after the timeout expires. Smoke test 11.9ms wake-latency on stdin-mid-wait. Affected modules: `panes/{token,warnings}_pane.py`, `workers/worker_pane.py` (two call sites: try body + except handler), `proxy_display/{pane,worker_proxy_pane}.py`. `metadata_pane.py` unchanged — has no stdin handler. Pattern A (direct sleep replacement) chosen over Pattern B (refresh-aligned timeout) because `warnings_pane`'s `WARNINGS_POLL_INTERVAL=10s` would otherwise mean up to 10s blocking on input — Pattern B would have made warnings unresponsive.

### LONG_OUTPUT_THRESHOLD (Kategorie: Display / UX)

`LONG_OUTPUT_THRESHOLD = 10000` in `src/constants.py`.
Verwendet in `format_output()` (formatter.py:119-138):
- `len(content) >= LONG_OUTPUT_THRESHOLD` → `log_long_output(content)` aufgerufen + `LIGHT_RED_BG` Hintergrundfarbe für den gesamten Output-Block
- `log_long_output()` (formatter.py:213-219) schreibt: char_count, line_count, 500-char Preview, und **den vollständigen Content** nach `src/logs/10_long_outputs.log`

Zentralisiert in constants.py.

### SCORE_PATTERN Regex (Kategorie: Display / UX)

`SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')` in `src/format/formatter.py:20`.
Verwendet in `format_output()` (formatter.py:130-131): Zeilen die matchen werden in `GREEN` coloriert.
Speziell für RAG-Suchergebnisse (Format aus rag-Plugin). Hardcoded Pattern.

### Pane Headers (Kategorie: Display / UX)

Sticky headers via tmux `pane-border-status top` + `pane-border-format` in `configure_tmux_session()`. Pane titles set via `select-pane -T` for all 11 panes (MAIN, TOKENS, PROXY, METADATA, RULES, HOOKS, WORKERS, WORKER-PROXY, WORKER-METADATA, WARNINGS, WASTE). Color: `colour216` (PASTEL_ORANGE). Headers never scroll away — tmux renders them in the pane border.

`format_pane_header()` in formatter.py still exists (PASTEL_ORANGE) but is no longer called from any loop. All header print calls removed from monitor.py (Session 6).

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

### Session-Browser (Session 3)

- `token_cumulative_n: Optional[int]` (monitor.py:48): steuert Modus. `None` = current session, `N` = letzte N Main-Sessions kumuliert
- Keyboard-Input in `run_tokens_loop()` (monitor.py:479-517): Ziffern → `token_input_buffer`, Enter → setzt `token_cumulative_n`, 'q' → setzt auf None, Backspace → löscht letzten Char
- `compute_cumulative_tokens(n)` (monitor.py:423-450): liest letzte N Main-Session-Files von Position 0 (kein Byte-Offset, full rescan), aggregiert Input/Output/Cache/Turns + per-tool output breakdown
- Input `0` → returns to current session view (`token_cumulative_n = None`)
- `format_token_profile_cumulative()` (formatter.py:324-371): rendert kumulative Ansicht mit granularem Output-Breakdown (per-tool + Text, same as current session view) + Per-Session-Breakdown (Input/Output/Turns pro File)
- Live-Prompt-Anzeige: `"Last N sessions › {buffer}_"` am Ende des Pane-Outputs

### Restart Hotkey (Kategorie: Display / UX)

`C-r` (Ctrl+R) keybinding in `configure_tmux_session()` (tmux_launcher.py): `respawn-pane -k` für alle 11 Panes across 5 Windows (0.0, 0.1, 1.0, 1.1, 2.0, 2.1, 3.0, 3.1, 3.2, 4.0, 4.1) via `\;`-Chain. Restarts all monitor processes with their original commands.

**BUG (fixed, Session 6):** User reports "Monitor restarted" message appears but panes don't visibly restart.
- Root cause: `C-r` binding is global (`-T root`) with hardcoded session name via Python f-string (`f"{session_name}:0.0"`). When multiple monitor sessions exist simultaneously, the last `configure_tmux_session()` call wins → C-r respawns panes of the wrong session. User sees "Monitor restarted" display-message but no visual change because the respawn happens in a different (possibly hidden) session.
- Diagnosis: `tmux list-keys | grep C-r` showed binding targeting `monitor_cc_79b52c8d` while active session was `monitor_cc_f93afc17`. After killing all stale sessions and restarting fresh, C-r worked correctly.
- Fix: Replace `f"{session_name}"` with `"#{session_name}"` in bind-key call. tmux resolves `#{session_name}` at runtime to the session where the keypress occurs.

### Screen Clear Escape Sequence (Kategorie: Display / Robustheit)

`\033[2J\033[3J\033[H` an folgenden Stellen:
- `src/core/monitor.py`: in `run_warnings_loop()` and `run_tokens_loop()`

Bedeutung: `[2J` löscht sichtbaren Screen, `[3J` löscht Scrollback-Buffer, `[H` setzt Cursor auf Position 0,0.

### Warnings-Pane (Kategorie: Format-Stabilität)

Eigenes tmux Pane (Window 4 "debug", Pane 4.0, links 50%) via `--mode warnings`:
- `run_warnings_loop()` in monitor.py: pollt `monitor_sessions()`, rendert `format_warnings_block()`
- `format_unknown_type_warning()` in formatter.py (formatter.py:229-230): `[!] Unknown JSONL type: <type> (seen Nx)`
- Screen-clear bei Änderung (`\033[2J\033[3J\033[H`)
- M-w Keybinding: Warnings-Pane Content → Clipboard via pbcopy (tmux_launcher.py, Pane 4.0)

### Workers-Pane (Kategorie: Worker-Monitoring, Session 3+7+9+10)

Eigenes tmux Pane (Window 3 "workers", Pane 3.0, links ~34%) via `--mode workers`. Window 3 has three panes: Workers (3.0) | Worker-Proxy (3.1) | Worker-Metadata (3.2). Subagents-Pane entfernt.
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
- M-k Keybinding: Workers-Pane Content → Clipboard via pbcopy (tmux_launcher.py, Pane 3.0)
- Dual poll intervals: Input polling at 50ms (`INPUT_POLL_INTERVAL`), data refresh at 500ms (`POLL_INTERVAL`).
- **Mouse UX:** Mode 1003 (Any Event Tracking) + SGR 1006. Input-Buffer Draining (while-loop). Hover-Highlight. Scroll (button 64/65 → increment/decrement scroll_offset). All reads via `os.read(fd, 1)` (unbuffered).
- Verifiziert gegen tmux Source Code (`repo/input-keys.c:755-822`): tmux forwarded SGR Mouse Events an App wenn `MODE_MOUSE_ALL` + `MODE_MOUSE_SGR` gesetzt sind. Kein Konflikt mit tmux `mouse on`.

### Main Pane Session-Reset (Session 11)

`run_main_loop()` tracks `current_main_session` via `_get_newest_main_session()`. Each poll cycle checks if newest main JSONL changed. On change: resets `file_positions[newest] = 0`, clears screen (`\033[2J\033[3J\033[H`), prints `--- New session detected ---` separator. Replays new session from beginning, old session messages not repeated.

### print_session_status Fix (Kategorie: Display / Startup)

`print_session_status()` und `print_startup_message()` werden nur für streaming/UI modes aufgerufen, nicht für dedizierte Panes (rules, warnings, hooks). Fix in `workflow.py` und `monitor.py`.

### Farb-Palette (Kategorie: Architektur — RESOLVED)

Alle Farb-Konstanten zentral in `src/constants.py` definiert (256-color ANSI). Alle Module importieren von dort. Keine Duplikation, keine Konflikte. Siehe Rule: `~/.claude/shared-rules/monitor/worker2/tui-standards.md`.

### Screenshot-Tool (Kategorie: Dev Tooling / Feedback)

`dev/display/screenshot_panes.py`: Captures all 11 tmux panes across 5 windows via `tmux capture-pane -p -e`, renders each to PNG via `termshot --raw-read`, combines with Pillow into single layout image → `/tmp/monitor_cc_screenshot.png`.

Dependencies: `termshot` (brew), `Pillow` (pip). Auto-detects running `monitor_cc_*` session.

Purpose: Claude reads the PNG per Read-Tool for visual layout verification during development.

### Rules Architecture: Hook-based Injection with Target Control (Session 15, 2026-04-05)

#### New Approach (Hook-based Injection with Target Control)

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

### Session 18 (2026-04-15) — Display Drift Update

Earlier IST sections reference the pre-Session-17 layout (4 windows, 6 panes) and pre-reversal scroll direction. This section documents the current prod state. Where an earlier section conflicts, THIS section is authoritative.

#### Current tmux Layout (src/tmux_launcher.py:45-66, 131-137)

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

#### Scroll Direction Reversed (traditional)

Wheel up = viewport moves toward earlier content (up), wheel down = viewport moves toward later content (down). Applied in ALL interactive panes: token, warnings, workers, hooks, metadata, proxy, worker-proxy. Reverses the Session-10..16 behaviour where wheel up scrolled toward newer content.

Implementation: each pane's mouse handler maps button 64 → `scroll_offset += N`, button 65 → `scroll_offset -= N` (or equivalent semantic).

#### ANSI Header Overdraw Pattern (Pane Header Contract)

Bug: when the body print overflows the pane height (terminal line wrap), the rendered top line of the body replaces the sticky header written by the pane loop itself. tmux `pane-border-status` still shows, but any app-level header line drawn on row 1 is lost.

Fix: after body print, overdraw the header using `\033[H{header}\033[K` (cursor home + header text + erase-to-EOL). Header always survives body overflow.

Applied: `src/panes/warnings_pane.py`, `src/proxy_display/pane.py` (function `run_worker_proxy_loop`). Pattern is generalizable — any pane that draws its own header on row 1 should use it.

#### Warnings Pane — 10s Polling + `r` Key

- Poll interval: 10s (was 0.5s). Warnings are rare and don't need sub-second latency; 0.5s burned CPU for no gain.
- Manual refresh: `r` key triggers immediate poll outside the 10s cycle.
- Header: `WARNINGS  [r]efresh · last: HH:MM:SS · polling: 10s`
- Source: `src/panes/warnings_pane.py`

#### Worker-Proxy Pane — Digit Switch Header

- Shows the proxy log of ONE selected worker at a time.
- Header: `WORKER-PROXY [1*]selected [2]other [3]another` — active selection marked with `*`.
- Digit keys 1-9 switch selection. IPC via `write_selection()` exposed from `src/workers/__init__.py`.
- Source: `src/proxy_display/pane.py` (function `run_worker_proxy_loop`)
- State clear rule: `worker_proxy_entries` (and all associated state) is cleared when `_worker_proxy_workers` is empty OR `current_worker` from selection file is not in worker list OR `worker_name != last_worker_name`. Ensures stale entries don't persist when all workers exit.
- Thinking block display: Thinking blocks render as `[N] thinking      text:Xc sig:Yc` to expose signature byte length (encrypted thinking carrier, ~400 chars typical on Opus 4.7 `display: summarized`). Field `sig_chars` added to block dict in `src/proxy/message_summary.py`. `chars` field remains `len(thinking_text)` only — signature NOT counted (signatures are not billed as input tokens per Anthropic docs).

#### Mouse Wheel Scroll Contract (all interactive panes)

Button codes (post-reversal):
- `64` (wheel up)   → `scroll_offset += N`   (viewport up, older content)
- `65` (wheel down) → `scroll_offset -= N`   (viewport down, newer content)
- `scroll_offset` clamped to `[0, max_scroll]`

N is typically 1 or 3 depending on pane density. See `src/panes/token_pane.py` as canonical reference pattern.

## Evidenz

### additionalContext per-Hook Limit

Live-Test Session 14 (2026-04-05), kein dev/-Script — manueller Test via settings.json hook-config + InstructionsLoaded-Observation. Binäre Suche über 4 Iterationen:
- 9,945 bytes → CC-Session erhält vollständigen Content ✅
- 10,081 bytes → truncated to 2KB preview ❌

Multiple SessionStart-Hooks mergen als separate `<system-reminder>` Tags (widerspricht GitHub-Source-Analyse "last one wins" — letztere ist falsch).

### Session-JSONL enthält keine Rules/Instructions-Daten

`dev/display/jsonl_exploration/` — Suite aus 3 Scripts (`01_map_message_types.py`, `02_map_content_blocks.py`, `03_scan_instructions.py`). Key Finding dokumentiert in `dev/display/jsonl_exploration/DOCS.md` (kein committed Report-MD im worktree):
- `Contents of`: **0 hits** (kein CLAUDE.md / .claude/rules/*.md Inhalt im JSONL)
- `system-reminder`: **0 hits** (nur zur API-Call-Zeit injiziert, nicht persistiert)
- `claudeMd`: **0 hits**

Dataset: mindestens 1 CC-Session-JSONL. Scripts laufen gegen beliebige Session-JSONL via positional arg.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

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
- GitHub anthropics/claude-code CHANGELOG v2.1.89: hook output > 50K → persisted-output (file path + preview statt direkter Injection). KORREKTUR: Live-Test (Session 14) zeigt ~10KB per-hook limit, nicht 50K.
- GitHub anthropics/claude-code #41799: Hooks docs omit >50K output file-path preview behavior
