# Pipe Section: Display

## State as of this section's audit

- `formatter.py`: color-coded output (green=main, red=error, pastel=meta)
- Workers pane (window 2, pane 2.0): `run_workers_loop()` (`workers/worker_pane.py:37`) + `format_workers_block()` (`workers/worker_format.py:71`) — shows worker name, status, spawn time, purpose. Two-pane split: Workers (2.0, 34%) | Worker-Proxy (2.1, 66%).
**BUG-CLASS (fixed, 2026-04-25 performance session):** All 9 stdin-driven panes were polling at a 50ms floor via `time.sleep(INPUT_POLL_INTERVAL)` at the end of each loop iteration → input latency 0–50ms (~25ms median) for hover/click/scroll/keyboard regardless of how fast the rest of the loop ran. Replaced with `wait_for_input(INPUT_POLL_INTERVAL)` from `src/input/click_handler.py` — a `select.select([_stdin_fd], [], [], timeout)` wrapper with `time.sleep` fallback when stdin not in raw mode. Loop wakes immediately on any byte arriving on stdin (mouse event, keypress) OR after the timeout expires. Smoke test 11.9ms wake-latency on stdin-mid-wait. Affected modules: `panes/{token,warnings}_pane.py`, `workers/worker_pane.py` (two call sites: try body + except handler), `proxy_display/{pane,worker_proxy_pane}.py`. Pattern A (direct sleep replacement) chosen over Pattern B (refresh-aligned timeout) because `warnings_pane`'s `WARNINGS_POLL_INTERVAL=10s` would otherwise mean up to 10s blocking on input — Pattern B would have made warnings unresponsive.

### LONG_OUTPUT_THRESHOLD (category: display / UX)

**Removed.** The constant and the length-based `LIGHT_RED_BG` wrap in `format_output()` have been deleted. Long tool outputs in the main pane now render identically to normal-length outputs — no background color, no length check.

### SCORE_PATTERN Regex (category: display / UX)

`SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')` in `src/format/formatter.py:12`.
Used in `format_output()` (formatter.py:107-108): matching lines are colored `GREEN`.
Specific to RAG search results (a format from the rag plugin). Hardcoded pattern.

### Pane Headers (category: display / UX)

Sticky headers via tmux `pane-border-status top` + `pane-border-format` in `configure_tmux_session()`. Pane titles set via `select-pane -T` for all 9 panes (MAIN, TOKENS, PROXY, WORKERS, WORKER-PROXY, WARNINGS, GPU, NEWS, NEWS-LOG). Color: `colour216` (PASTEL_ORANGE). Headers never scroll away — tmux renders them in the pane border.


### Token-Profiling Pane (category: display / token visibility)

Its own tmux pane (window 0 "main", pane 0.1, right 30%) via `--mode tokens`:
- `shorten_tool_name()` in formatter.py: shortens MCP tool names (`mcp__plugin_xxx__tool` → `tool`)
- Screen-clear on change (`\033[2J\033[3J\033[H`)
- M-t keybinding: tokens-pane content → clipboard via pbcopy
- JSONL data source: `message.usage.output_tokens` per content block (assistant messages)
- Known limitation: output_tokens ~1.9x undercount (Claude Code bug #27361), irrelevant for proportions
- **Token dedup (session 11, updated session 17):** `extract_cache_turns()` deduplicates streaming chunks using `requestId` as the primary key (falls back to `(cache_read, cache_creation, input_tokens)` for entries without requestId). Uses MAX(output_tokens), aggregates unique content_blocks. `request_id` stored as a persistent field on api_call dicts for incremental merge in `build_cache_turns()`.
- **% removed (session 11):** `_format_cache_call()` no longer calculates or displays the cache-read percentage. Shows only raw JSONL values: CR, CC, D, output_tokens.
- **Thinking display (session 11):** thinking content_blocks now include `output_tokens` from message-level usage. Rendered as `thinking (Xk out)` in the expanded API-call view.

### Proxy Pane — Forwarded-Log Migration (Stage 2, 2026-06)

**Source migrated from the main log to the `_forwarded` dual-log (Stage 2C):**
- `parse_proxy_log_forwarded` / `_parse_forwarded_log` replace `parse_proxy_log_isolated`; state `_proxy_fwd_pos`+`_proxy_acc_fwd` replace `_proxy_pending_by_rid` in `pane.py` and `worker_proxy_pane.py`.
- Worker pane uses `_parse_forwarded_log` directly with fwd_path derived from the `find_worker_proxy_log` result: `log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'`.
- Lazy-reload: `_lazy_load_messages_forwarded(entry, fwd_path)` replaces `_lazy_load_messages(entry, log_path)` — replays the forwarded delta stream to the target `_fwd_req_idx` rather than seeking a `_byte_offset`.
- Deque bound: only the last `PROXY_MESSAGES_KEEP_LAST=10` entries have `messages` populated; earlier entries carry `messages=None` (lazy-loadable). Replaces the main-log strip-on-extend pattern.
- Graceful degrade: a missing `_forwarded` file → `_parse_forwarded_log` returns `([], last_pos)` → empty pane, no crash. An old `_forwarded` without `max_tokens`/`output_config` → `eff`/`think` simply absent from the header.

**BP:N counter + latency badge removed (Stage 2A):**
- The `BP:N` counter dropped from the REQ header row in `render_turn.py` — pre-ops cache_breakpoints are not reconstructable from `_forwarded`. The `cache_breakpoints` field is still present in entry dicts (used for `opus_req_num` increment logic / sub-number #N.M assignment) but no longer displayed.
- The latency badge (`_format_latency` / `ttfb_ms` / `output_tokens_per_sec` / `n_stalls`) removed from `render_turn.py` and `format.py`.

### Warnings Pane — _errors Dual-Log Migration (Stage 2D, 2026-06)

**Source migrated to the `_errors` dual-log (current-session-only):**
- `_refresh_warnings_data` reads `find_errors_log_path(project_filter)` → the main session's `_errors` log from byte 0 (current session by design; incremental via `_errors_log_pos`).
- Worker errors via `scan_worker_errors_logs(last_positions, project_session_id, min_mtime)` — globs `dual_log/api_requests_worker_{sid}_*_errors.jsonl`.
- Each `_errors` record converted by `_errors_record_to_display` to the `tool_errors` display dict. `worker_name` extracted from the `record['worker']` field (`worker:<name>` prefix).
- **Dropped:** the proxy-log scan (`parse_proxy_log` call + `_proxy_log_position`), the worker-log scan (`scan_worker_logs` + `_worker_log_positions`), `_scan_proxy_entries_for_errors`, `_scan_proxy_entries_for_zero_results`, the zero_results section, the schema_warnings section, dedup sets `_seen_zero_keys`/`_seen_error_keys`, `_proxy_pending_by_rid`.
- `warnings_scan.py` / `warnings_persist.py` / `warnings_parse.py` no longer exist; the unknown-type warning path (`track_unknown_type`/`unknown_type_counts`/`format_unknown_type_warning`) was removed entirely. The warnings module is now just `warnings_pane.py` + `warnings_render.py`.
- `_format_warnings_pane` signature: removed the `schema_warnings`, `zero_results`, `zero_result_expand_states` params; returns a 2-tuple `(rendered_str, error_line_map)` instead of a 3-tuple.

### Proxy Pane Redesign (Session 17, 2026-04-09)

**Turn-based expand/collapse:** the proxy pane was redesigned from per-request expand to a two-level turn-based hierarchy. The turn header is clickable (expand/collapse). An expanded turn shows: request metadata lines (compact, also clickable) + message lines. Request expand shows messages belonging to that specific request.

**REQ numbering sync:** `opus_req_num` reset at each turn boundary using the cumulative `api_calls` count from session JSONL turns. Eliminates cross-turn drift from proxy-only requests (that don't appear in session JSONL). Helper requests (non-haiku, BP:0) get sub-numbers (#7.1, #7.2).

**Modified message detection:** when consecutive requests have the same message_count but different total chars, a backwards scan from the end finds the divergence point. The `content_tail` field (last 500 chars) enables showing the actual new content appended to modified messages.

**Turn header config:** shows `effort:X`, `think:Yk(type)` from the API payload's `output_config.effort` and `thinking.budget_tokens`/`thinking.type`. Red highlight when values change between turns.

**Image grouping (main pane):** `format_user_media()` in `format/formatter_events.py:36` now accepts a list of media items grouped by timestamp. Multiple images rendered as a single line: `[4x IMAGE: image/png]`.

### Session Browser (Session 3) — REMOVED

The cumulative-token session-browser feature was removed: `token_cumulative_n`, `compute_cumulative_tokens(n)`, and the associated keyboard handling in `run_tokens_loop()` no longer exist (grep `cumulative|token_cumulative src/ --include=*.py` → no hits in the token path). `run_tokens_loop()` now lives in `panes/token_pane.py:31`.

### Restart Hotkey (category: display / UX)

`C-r` (Ctrl+R) keybinding in `configure_tmux_session()` (tmux_launcher.py:174-175): `bind-key -T root C-r run-shell <restart_cmd>`, where `restart_cmd` calls `--mode restart-panes` → `restart_panes()` (tmux_launcher.py:208). `restart_panes()` heals missing panes from `_WINDOW_LAYOUT` (6 windows: 0.0, 0.1, 1.0, 2.0, 2.1, 3.0, 4.0, 5.0, 5.1 — 9 panes) and then respawns all panes with `respawn-pane -k`. No more `\;` chain. Restarts all monitor processes with their original commands.

**BUG (fixed, session 6):** user reports "Monitor restarted" message appears but panes don't visibly restart.
- Root cause: the `C-r` binding is global (`-T root`) with a hardcoded session name via a Python f-string (`f"{session_name}:0.0"`). When multiple monitor sessions exist simultaneously, the last `configure_tmux_session()` call wins → C-r respawns panes of the wrong session. The user sees the "Monitor restarted" display-message but no visual change because the respawn happens in a different (possibly hidden) session.
- Diagnosis: `tmux list-keys | grep C-r` showed the binding targeting `monitor_cc_79b52c8d` while the active session was `monitor_cc_f93afc17`. After killing all stale sessions and restarting fresh, C-r worked correctly.
- Fix: replace `f"{session_name}"` with `"#{session_name}"` in the bind-key call. tmux resolves `#{session_name}` at runtime to the session where the keypress occurs.

### News Pane — Window 5 (2-Pane Split, 2026-06)

Window 5 "news": left pane NEWS (5.0, 50%) controls and observes the CoinDesk → `searxng_crypto` news ingestion pipeline (external project: searxng-cli). Right pane NEWS-LOG (5.1, 50%) tails the pipeline log.

**NEWS pane (5.0, `--mode news`, `src/news_pane/pane.py`):**
- Displays: `searxng_crypto` doc count (`rag-cli list_documents searxng_crypto`), chunk count (`rag-cli list_collections --json`), last-run timestamp (`src/logs/news_coindesk_last_run.txt` in searxng-cli).
- `[run pipeline]` button (SGR mouse, right-aligned): launches `venv/bin/python -m src.news --source coindesk` with `cwd=SEARXNG_ROOT`, stdout+stderr DEVNULL. Popen handle held in `_pipeline_proc`.
- Running indicator: label flips to `⟳ running… [running…]` (YELLOW) while `_pipeline_proc.poll() is None`. Log fallback: start-marker present, no end-marker, log mtime < 60s.
- Button region only registered when idle — no separate guard flag.
- `enable_mouse()` active (SGR mode 1003+1006); tmux native scroll NOT available while the pane is active.
- Poll interval: 2s.

**NEWS-LOG pane (5.1, `--mode news-log`, `src/news_pane/log_pane.py`):**
- No mouse (tmux native scroll active in this pane).
- Finds the newest `news_coindesk_*.log` by mtime; extracts lines from the last `=== coindesk pipeline started ===`; filters via a whitelist (STAGE/→/[OK]/[FAIL]/preconditions/Nothing new/markers) + WARNING/ERROR level.
- Renders filtered events top-anchored (directly under the header + filename, growing top-down; newest visible on overflow), `MAX_LOG_LINES = 40`.
- Poll interval: 0.5s.

**Log whitelist patterns (applied to `msg` after `_LOG_LINE_RE` strips leading whitespace):**
`Checking preconditions`, `\[(OK|FAIL)\]`, `STAGE (discover|dedup|scrape|cleanup|publish)`, `(stage-name) →`, `Nothing new to scrape`, `RegwallGuardError`, `=== coindesk pipeline`.

**Keybinding:** `M-n` → `capture-pane -t session:5.1 -pS - | pbcopy` (news-log pane copy).

### Screen Clear Escape Sequence (category: display / robustness)

`\033[2J\033[3J\033[H` used in:
- `src/panes/warnings_pane.py`: in `run_warnings_loop()`; `src/panes/token_pane.py`: in `run_tokens_loop()`

Meaning: `[2J` clears the visible screen, `[3J` clears the scrollback buffer, `[H` sets the cursor to position 0,0.

### Warnings Pane (category: format stability)

Its own tmux pane (window 3 "debug", pane 3.0, fullscreen) via `--mode warnings`:
- `run_warnings_loop()` in `panes/warnings_pane.py:34`: polls sessions, renders via `_format_warnings_pane()` (`panes/warnings_render.py:26`)
- Screen-clear on change (`\033[2J\033[3J\033[H`)
- M-w keybinding: warnings-pane content → clipboard via pbcopy (tmux_launcher.py, pane 3.0)

### Workers Pane (category: worker monitoring, session 3+7+9+10)

Its own tmux pane (window 2 "workers", pane 2.0, left ~34%) via `--mode workers`. Window 2 has two panes: Workers (2.0) | Worker-Proxy (2.1). The subagents pane has been removed.
- `run_workers_loop()` in `workers/worker_pane.py:37`: polls `list_workers()`, renders `format_workers_block()`. Keyboard input (digits 1-9 toggle) + SGR mouse-click toggle + scroll.
- `list_workers(project_path)` (`workers/worker_tmux.py:47`): scans tmux sessions with the prefix `worker-{project_name}-`, reads status + env variables per worker
- `detect_worker_status(session)` (`workers/worker_tmux.py:24`): checks `#{pane_dead}` for exited status; analyzes the `#{window_activity}` timestamp for idle detection (10s threshold)
- `get_tmux_env(session, var)` (`workers/worker_tmux.py:14`): reads WORKER_SPAWNED, WORKER_PURPOSE from tmux show-environment
- `get_worker_project_name(project_path)` (`workers/worker_format.py:17`): extracts the project name worktree-aware (splits at `/.claude/worktrees/`)
- `find_worker_jsonl(session_name)` (`workers/worker_tmux.py:75`): worker JSONL discovery via `pane_current_path` → `encode_project_path()` → `~/.claude/projects/<encoded>/`. Worktree-aware: direct lookup on the worktree directory (no fallback to the base project).
- `format_workers_block(workers, expand_states=None, worker_turns=None, scroll_offsets=None, cache_expand_states=None, frozen=False, selected_name=None)` (`workers/worker_format.py:71`): expand/collapse per worker. Collapsed: `[+] [idx] name STATUS spawn_time` + truncated purpose. Expanded: `[-] [idx] name STATUS spawn_time` + full purpose + scrollable cache-tracker token view (CR/CC/D per API call via `format_cache_tracker()`).
- State: `worker_expand_states: Dict[str, bool]`, `worker_scroll_offsets: Dict[str, int]` (`workers/worker_pane.py`)
- Status colors: working=GREEN, idle=YELLOW, exited=RED, unknown=WHITE
- Screen-clear on change (`\033[2J\033[3J\033[H`)
- M-k keybinding: workers-pane content → clipboard via pbcopy (tmux_launcher.py, pane 2.0)
- Dual poll intervals: input polling at 50ms (`INPUT_POLL_INTERVAL`), data refresh at 500ms (`POLL_INTERVAL`).
- **Mouse UX:** mode 1003 (any event tracking) + SGR 1006. Input-buffer draining (while-loop). Hover-highlight. Scroll (button 64/65 → increment/decrement scroll_offset). All reads via `os.read(fd, 1)` (unbuffered).
- Verified against the tmux source code (`repo/input-keys.c:755-822`): tmux forwards SGR mouse events to the app when `MODE_MOUSE_ALL` + `MODE_MOUSE_SGR` are set. No conflict with tmux `mouse on`.

### Main Pane Session Reset (Session 11)

`run_main_loop()` tracks `current_main_session` via `_get_newest_main_session()`. Each poll cycle checks whether the newest main JSONL changed. On change: resets `file_positions[newest] = 0`, clears the screen (`\033[2J\033[3J\033[H`), prints a `--- New session detected ---` separator. Replays the new session from the beginning, old-session messages are not repeated.

### print_session_status Fix (category: display / startup)

`print_session_status()` and `print_startup_message()` are only called for streaming/UI modes, not for dedicated panes (rules, warnings, hooks). Fixed in `workflow.py` and `monitor.py`.

### Color Palette (category: architecture — RESOLVED)

All color constants defined centrally in `src/constants.py` (256-color ANSI). All modules import from there. No duplication, no conflicts. See rule: `~/.claude/shared-rules/monitor/worker2/tui-standards.md`.

### Screenshot Tool (category: dev tooling / feedback)

`dev/display/screenshot_panes.py`: captures all 9 tmux panes across 5 windows via `tmux capture-pane -p -e`, renders each to PNG via `termshot --raw-read`, combines with Pillow into a single layout image → `/tmp/monitor_cc_screenshot.png`.

Dependencies: `termshot` (brew), `Pillow` (pip). Auto-detects the running `monitor_cc_*` session.

Purpose: Claude reads the PNG via the Read tool for visual layout verification during development.

### Rules Architecture: Hook-Based Injection with Target Control (Session 15, 2026-04-05)

#### New Approach (Hook-Based Injection with Target Control)

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
- `session-start-monitor-worker.sh` (new) — worker-only: injects RULE_DIR only when CWD contains `/.claude/worktrees/`, project-filtered
- `session-start-monitor-shared.sh` (new) — shared: injects RULE_DIR for all sessions matching PROJECT_FILTER (no worktree exclusion)

**6 SessionStart hooks in `~/.claude/settings.json`:**
1. `RULE_DIR=monitor/opus PROJECT_FILTER=Monitor_CC session-start-project-rules.sh` → Opus only
2. `RULE_DIR=monitor/worker1 PROJECT_FILTER=Monitor_CC session-start-monitor-worker.sh` → workers only
3. `RULE_DIR=monitor/worker2 PROJECT_FILTER=Monitor_CC session-start-monitor-worker.sh` → workers only
4. `RULE_DIR=monitor/shared-a PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → both
5. `RULE_DIR=monitor/shared-b PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → both
6. `RULE_DIR=monitor/shared-c PROJECT_FILTER=Monitor_CC session-start-monitor-shared.sh` → both

**Size constraint:** each hook injects ≤9,500 bytes (10KB per-hook limit, safety margin). Split into subdirectories to respect this: worker1+worker2 for worker rules (5,124 + 6,505 bytes), shared-a/b/c for global rules (6,817 + 9,065 + 3,678 bytes).

**Monitor_CC/.claude/rules/:** now empty. All rules delivered via hook injection.

### Session 18 (2026-04-15) — Display Drift Update

Earlier sections reference the pre-Session-17 layout (4 windows, 6 panes) and pre-reversal scroll direction. This section documents the production state as of session 18. Where an earlier section conflicts, THIS section is authoritative as of that date.

#### tmux Layout as of Session 18 (`configure_tmux_session()` `pane_titles` dict)

6 windows, 9 panes.

| Window | Name | Panes |
|---|---|---|
| 0 | main | 0.0 MAIN (70%), 0.1 TOKENS (30%) |
| 1 | proxy | 1.0 PROXY (fullscreen) |
| 2 | workers | 2.0 WORKERS (34%), 2.1 WORKER-PROXY (66%) |
| 3 | debug | 3.0 WARNINGS (fullscreen) |
| 4 | gpu | 4.0 GPU (fullscreen) |
| 5 | news | 5.0 NEWS (50%), 5.1 NEWS-LOG (50%) |

#### Scroll Direction Reversed (Traditional)

Wheel up = viewport moves toward earlier content (up), wheel down = viewport moves toward later content (down). Applied in ALL interactive panes: token, warnings, workers, hooks, proxy, worker-proxy. Reverses the session-10..16 behavior where wheel up scrolled toward newer content.

Implementation: each pane's mouse handler maps button 64 → `scroll_offset += N`, button 65 → `scroll_offset -= N` (or an equivalent semantic).

#### ANSI Header Overdraw Pattern (Pane Header Contract)

Bug: when the body print overflows the pane height (terminal line wrap), the rendered top line of the body replaces the sticky header written by the pane loop itself. tmux `pane-border-status` still shows, but any app-level header line drawn on row 1 is lost.

Fix: after the body print, overdraw the header using `\033[H{header}\033[K` (cursor home + header text + erase-to-EOL). The header always survives body overflow.

Applied: `src/panes/warnings_pane.py`, `src/proxy_display/pane.py` (function `run_proxy_loop`). The pattern is generalizable — any pane that draws its own header on row 1 should use it.

#### Warnings Pane — 10s Polling + `r` Key

- Poll interval: 10s (was 0.5s). Warnings are rare and don't need sub-second latency; 0.5s burned CPU for no gain.
- Manual refresh: the `r` key triggers an immediate poll outside the 10s cycle.
- Header: `WARNINGS  [r]efresh · last: HH:MM:SS · polling: 10s`
- Source: `src/panes/warnings_pane.py`

#### Worker-Proxy Pane — Digit Switch Header

- Shows the proxy log of ONE selected worker at a time.
- Header: `WORKER-PROXY [1*]selected [2]other [3]another` — active selection marked with `*`.
- Digit keys 1-9 switch selection. IPC via `write_selection()` exposed from `src/workers/__init__.py`.
- Source: `src/proxy_display/worker_proxy_pane.py` (function `run_worker_proxy_loop`)
- State-clear rule: `worker_proxy_entries` (and all associated state) is cleared when `_worker_proxy_workers` is empty OR the `current_worker` from the selection file is not in the worker list OR `worker_name != last_worker_name`. Ensures stale entries don't persist when all workers exit.
- Thinking-block display: thinking blocks render as `[N] thinking      text:Xc sig:Yc` to expose the signature byte length (encrypted thinking carrier, ~400 chars typical on Opus 4.7 `display: summarized`). The field `sig_chars` added to the block dict in `src/proxy/message_summary.py`. The `chars` field remains `len(thinking_text)` only — the signature is NOT counted (signatures are not billed as input tokens per Anthropic docs).

#### Mouse Wheel Scroll Contract (All Interactive Panes)

Button codes (post-reversal):
- `64` (wheel up)   → `scroll_offset += N`   (viewport up, older content)
- `65` (wheel down) → `scroll_offset -= N`   (viewport down, newer content)
- `scroll_offset` clamped to `[0, max_scroll]`

N is typically 1 or 3 depending on pane density. See `src/panes/token_pane.py` as the canonical reference pattern.

## Evidence

### additionalContext Per-Hook Limit

Live test, session 14 (2026-04-05), no dev/ script — manual test via settings.json hook-config + InstructionsLoaded observation. Binary search over 4 iterations:
- 9,945 bytes → the CC session receives the full content
- 10,081 bytes → truncated to a 2KB preview

Multiple SessionStart hooks merge as separate `<system-reminder>` tags (contradicts a GitHub source-code claim of "last one wins" — that claim is wrong).

### Session JSONL Contains No Rules/Instructions Data

`dev/display/jsonl_exploration/` — a suite of 3 scripts (`01_map_message_types.py`, `02_map_content_blocks.py`, `03_scan_instructions.py`). Key finding documented in `dev/display/jsonl_exploration/DOCS.md` (no committed report MD in the worktree):
- `Contents of`: **0 hits** (no CLAUDE.md / .claude/rules/*.md content in the JSONL)
- `system-reminder`: **0 hits** (only injected at API-call time, not persisted)
- `claudeMd`: **0 hits**

Dataset: at least 1 CC session JSONL. The scripts run against any session JSONL via a positional arg.

## Recommendation (target state)

Pending — needs evaluation.

## Open Questions

- The InstructionsLoaded hook does not fire after `/clear` or `/compact` (#30973, #31017) — the monitor can't track reloads
- The session JSONL contains no rules/instructions data (verified via the `dev/display/jsonl_exploration` scripts)

## Sources

- GitHub anthropics/claude-code #19377 — YAML array syntax for `paths:` broken (CSV parser bug)
- GitHub anthropics/claude-code #33581 — multiple `paths:` entries silently fail (same root cause)
- GitHub anthropics/claude-code #30973 — InstructionsLoaded missing after compaction
- GitHub anthropics/claude-code #31017 — InstructionsLoaded missing on `/clear`
- GitHub anthropics/claude-code #16299 — path-scoped rules load globally (opposite bug, version-dependent)
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (no official monitoring API)
- GitHub anthropics/claude-code CHANGELOG v2.1.89: hook output > 50K → persisted-output (file path + preview instead of direct injection). CORRECTION: the live test (session 14) shows a ~10KB per-hook limit, not 50K.
- GitHub anthropics/claude-code #41799: hooks docs omit the >50K output file-path preview behavior
